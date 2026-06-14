import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merchant import Merchant, MerchantTier
from app.models.product import MerchantProduct, MerchantProductEmbedding, MerchantProductImage
from app.schemas.chat import ProductCard
from app.services.embeddings import ProductEmbeddingError, embedding_client

MAX_MATCHES = 3
VECTOR_CANDIDATE_LIMIT = 50
RULE_CANDIDATE_LIMIT = 80
QUERY_EMBEDDING_CACHE: dict[str, list[float]] = {}

CATEGORY_TERMS = {
    "手镯": ["手镯", "镯子", "圆条", "正圈", "贵妃"],
    "吊坠": ["吊坠", "挂件", "坠子"],
    "平安扣": ["平安扣"],
    "戒面": ["戒面", "蛋面", "戒指"],
    "珠串": ["珠串", "手串", "珠链", "串珠"],
}
COLOR_TERMS = ["帝王绿", "阳绿", "辣绿", "满绿", "飘花", "晴底", "蓝水", "紫罗兰", "春彩", "黄翡"]
WATER_TERMS = ["玻璃种", "高冰", "冰种", "糯冰", "糯种", "豆种"]
SHAPE_TERMS = ["圆条", "正圈", "贵妃", "平安扣", "蛋面", "珠串"]
FLAW_TERMS = ["无纹无裂", "无纹", "无裂", "不要纹裂", "微瑕", "有纹", "有裂"]
PURPOSE_TERMS = ["送礼", "自用", "收藏", "日常佩戴", "婚嫁"]
CERTIFICATE_TERMS = ["证书", "有证书", "国检", "鉴定证书"]
NEED_INTENT_TERMS = [
    "找",
    "想要",
    "需要",
    "有没有",
    "推荐",
    "匹配",
    "预算",
    "买",
    "购买",
    "货源",
    "求",
]

CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


@dataclass(frozen=True)
class VisitorNeed:
    raw_text: str
    budget_cents: int | None
    category: str | None
    colors: list[str]
    waters: list[str]
    shapes: list[str]
    flaws: list[str]
    purposes: list[str]
    certificates: list[str]
    keywords: list[str]
    search_text: str


@dataclass(frozen=True)
class MatchResult:
    content: str
    products: list[ProductCard]


@dataclass(frozen=True)
class ProductCandidate:
    product: MerchantProduct
    merchant_tier: str
    image_url: str
    vector_distance: float | None


def parse_visitor_need(content: str) -> VisitorNeed:
    text = re.sub(r"\s+", " ", content.strip())[:1000]
    budget_cents = _extract_budget_cents(text)
    category = _first_category(text)
    colors = _matched_terms(text, COLOR_TERMS)
    waters = _matched_terms(text, WATER_TERMS)
    shapes = _matched_terms(text, SHAPE_TERMS)
    flaws = _matched_terms(text, FLAW_TERMS)
    purposes = _matched_terms(text, PURPOSE_TERMS)
    certificates = _matched_terms(text, CERTIFICATE_TERMS)
    keywords = _keywords(text, category, colors, waters, shapes, flaws, purposes, certificates)
    search_text = _build_need_search_text(
        raw_text=text,
        budget_cents=budget_cents,
        category=category,
        colors=colors,
        waters=waters,
        shapes=shapes,
        flaws=flaws,
        purposes=purposes,
        certificates=certificates,
        keywords=keywords,
    )
    return VisitorNeed(
        raw_text=text,
        budget_cents=budget_cents,
        category=category,
        colors=colors,
        waters=waters,
        shapes=shapes,
        flaws=flaws,
        purposes=purposes,
        certificates=certificates,
        keywords=keywords,
        search_text=search_text,
    )


def looks_like_product_need(content: str) -> bool:
    text = content.strip()
    need = parse_visitor_need(content)
    has_intent = any(term in text for term in NEED_INTENT_TERMS)
    has_feature = any(
        [
            need.colors,
            need.waters,
            need.shapes,
            need.flaws,
            need.purposes,
            need.certificates,
        ]
    )
    if need.budget_cents and (need.category or has_feature or has_intent):
        return True
    if need.category and (has_feature or has_intent):
        return True
    return False


async def match_products_for_need(content: str, db: AsyncSession) -> MatchResult:
    need = parse_visitor_need(content)
    candidates = await _vector_candidates(need, db)
    used_fallback = False
    if not candidates:
        candidates = await _rule_candidates(need, db)
        used_fallback = True

    ranked = sorted(
        candidates,
        key=lambda candidate: _score_candidate(candidate, need),
        reverse=True,
    )
    products = [_product_card(candidate) for candidate in ranked[:MAX_MATCHES]]

    if not products:
        content_text = "暂未找到合适货源，建议补充预算、品类或尺寸。"
    elif used_fallback:
        content_text = "暂未找到完全匹配货源，先为您推荐相近商品。"
    else:
        content_text = "已根据预算、品类和商品特征为您匹配相近货源。"
    return MatchResult(content=content_text, products=products)


def _extract_budget_cents(text: str) -> int | None:
    patterns = [
        r"预算[^\d一二两三四五六七八九十]{0,6}([0-9]+(?:\.[0-9]+)?|[一二两三四五六七八九十]+)\s*(万|w|W|千|k|K|元)?",
        r"([0-9]+(?:\.[0-9]+)?|[一二两三四五六七八九十]+)\s*(万|w|W|千|k|K|元)\s*(?:预算|以内|左右|以下)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        number = _number_value(match.group(1))
        if number is None:
            continue
        unit = match.group(2) or ""
        if unit in {"万", "w", "W"}:
            amount = number * 10_000
        elif unit in {"千", "k", "K"}:
            amount = number * 1_000
        else:
            amount = number
        return int(amount * 100)
    return None


def _number_value(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        pass
    if value == "十":
        return 10
    if value.startswith("十") and len(value) == 2:
        return 10 + CHINESE_NUMBERS.get(value[1], 0)
    if value.endswith("十") and len(value) == 2:
        return CHINESE_NUMBERS.get(value[0], 0) * 10
    if "十" in value and len(value) == 3:
        return CHINESE_NUMBERS.get(value[0], 0) * 10 + CHINESE_NUMBERS.get(value[2], 0)
    total = 0
    for char in value:
        if char not in CHINESE_NUMBERS:
            return None
        total = total * 10 + CHINESE_NUMBERS[char]
    return float(total) if total else None


def _first_category(text: str) -> str | None:
    for category, aliases in CATEGORY_TERMS.items():
        if any(alias in text for alias in aliases):
            return category
    return None


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _keywords(
    text: str,
    category: str | None,
    colors: list[str],
    waters: list[str],
    shapes: list[str],
    flaws: list[str],
    purposes: list[str],
    certificates: list[str],
) -> list[str]:
    terms = [category or "", *colors, *waters, *shapes, *flaws, *purposes, *certificates]
    keywords = [term for term in terms if term]
    for token in re.split(r"[\s,，。；;、]+", text):
        token = token.strip()
        if 1 < len(token) <= 12 and not any(char.isdigit() for char in token):
            keywords.append(token)
    deduped: list[str] = []
    for keyword in keywords:
        if keyword not in deduped:
            deduped.append(keyword)
    return deduped[:12]


def _build_need_search_text(
    *,
    raw_text: str,
    budget_cents: int | None,
    category: str | None,
    colors: list[str],
    waters: list[str],
    shapes: list[str],
    flaws: list[str],
    purposes: list[str],
    certificates: list[str],
    keywords: list[str],
) -> str:
    budget_text = f"{budget_cents // 100}元" if budget_cents else "未知"
    return "\n".join(
        [
            f"需求：{raw_text}",
            f"预算：{budget_text}",
            f"品类：{category or '未知'}",
            f"颜色：{_join_or_unknown(colors)}",
            f"种水：{_join_or_unknown(waters)}",
            f"器型：{_join_or_unknown(shapes)}",
            f"瑕疵：{_join_or_unknown(flaws)}",
            f"用途：{_join_or_unknown(purposes)}",
            f"证书：{_join_or_unknown(certificates)}",
            f"关键词：{_join_or_unknown(keywords)}",
        ]
    )


def _join_or_unknown(values: list[str]) -> str:
    return "、".join(values) if values else "未知"


async def _vector_candidates(need: VisitorNeed, db: AsyncSession) -> list[ProductCandidate]:
    try:
        embedding = await _query_embedding(need.search_text)
    except ProductEmbeddingError:
        return []

    distance = MerchantProductEmbedding.embedding.cosine_distance(embedding)
    statement = (
        select(MerchantProduct, Merchant.tier, distance.label("distance"))
        .join(MerchantProductEmbedding, MerchantProductEmbedding.product_id == MerchantProduct.id)
        .join(Merchant, Merchant.id == MerchantProduct.merchant_id)
        .where(MerchantProduct.status == "listed")
    )
    if need.category:
        statement = statement.where(_category_filter(need.category))
    statement = statement.order_by(distance).limit(VECTOR_CANDIDATE_LIMIT)
    result = await db.execute(statement)
    rows = result.all()
    image_urls = await _first_image_urls([row[0].id for row in rows], db)
    return [
        ProductCandidate(
            product=product,
            merchant_tier=str(tier.value if isinstance(tier, MerchantTier) else tier),
            image_url=image_urls.get(product.id) or _legacy_image_url(product),
            vector_distance=float(distance_value) if distance_value is not None else None,
        )
        for product, tier, distance_value in rows
    ]


async def _query_embedding(search_text: str) -> list[float]:
    cached = QUERY_EMBEDDING_CACHE.get(search_text)
    if cached is not None:
        return cached
    result = await embedding_client.embed_document(search_text, timeout_seconds=5)
    if len(QUERY_EMBEDDING_CACHE) >= 128:
        QUERY_EMBEDDING_CACHE.clear()
    QUERY_EMBEDDING_CACHE[search_text] = result.embedding
    return result.embedding


async def _rule_candidates(need: VisitorNeed, db: AsyncSession) -> list[ProductCandidate]:
    statement = (
        select(MerchantProduct, Merchant.tier)
        .join(Merchant, Merchant.id == MerchantProduct.merchant_id)
        .where(MerchantProduct.status == "listed")
        .order_by(desc(MerchantProduct.updated_at))
        .limit(RULE_CANDIDATE_LIMIT)
    )
    if need.category:
        statement = statement.where(_category_filter(need.category))
    if need.keywords:
        like_filters = []
        for keyword in need.keywords[:8]:
            pattern = f"%{keyword}%"
            like_filters.extend(
                [
                    MerchantProduct.title.ilike(pattern),
                    MerchantProduct.summary.ilike(pattern),
                    MerchantProduct.detail.ilike(pattern),
                    MerchantProduct.search_text.ilike(pattern),
                ]
            )
        statement = statement.where(or_(*like_filters))
    result = await db.execute(statement)
    rows = result.all()

    if not rows and need.category:
        result = await db.execute(
            select(MerchantProduct, Merchant.tier)
            .join(Merchant, Merchant.id == MerchantProduct.merchant_id)
            .where(MerchantProduct.status == "listed")
            .where(_category_filter(need.category))
            .order_by(desc(MerchantProduct.updated_at))
            .limit(RULE_CANDIDATE_LIMIT)
        )
        rows = result.all()
    if not rows:
        result = await db.execute(
            select(MerchantProduct, Merchant.tier)
            .join(Merchant, Merchant.id == MerchantProduct.merchant_id)
            .where(MerchantProduct.status == "listed")
            .order_by(desc(MerchantProduct.updated_at))
            .limit(RULE_CANDIDATE_LIMIT)
        )
        rows = result.all()

    image_urls = await _first_image_urls([row[0].id for row in rows], db)
    return [
        ProductCandidate(
            product=product,
            merchant_tier=str(tier.value if isinstance(tier, MerchantTier) else tier),
            image_url=image_urls.get(product.id) or _legacy_image_url(product),
            vector_distance=None,
        )
        for product, tier in rows
    ]


def _category_filter(category: str):
    aliases = CATEGORY_TERMS.get(category, [category])
    filters = []
    for alias in aliases:
        pattern = f"%{alias}%"
        filters.extend(
            [
                MerchantProduct.title.ilike(pattern),
                MerchantProduct.summary.ilike(pattern),
                MerchantProduct.detail.ilike(pattern),
                MerchantProduct.search_text.ilike(pattern),
            ]
        )
    return or_(*filters)


async def _first_image_urls(product_ids: list[UUID], db: AsyncSession) -> dict[UUID, str]:
    if not product_ids:
        return {}
    result = await db.execute(
        select(MerchantProductImage.product_id, MerchantProductImage.public_url)
        .where(MerchantProductImage.product_id.in_(product_ids))
        .order_by(MerchantProductImage.product_id, MerchantProductImage.sort_order)
    )
    urls: dict[UUID, str] = {}
    for product_id, public_url in result.all():
        urls.setdefault(product_id, public_url)
    return urls


def _legacy_image_url(product: MerchantProduct) -> str:
    return product.image_urls[0] if product.image_urls else "/mock-products/jade-1.png"


def _score_candidate(candidate: ProductCandidate, need: VisitorNeed) -> float:
    product = candidate.product
    text = _product_text(product)
    score = 0.0
    if candidate.vector_distance is not None:
        score += max(0.0, 1.0 - candidate.vector_distance) * 100
    else:
        score += 20

    for term in [*need.colors, *need.waters, *need.shapes, *need.flaws, *need.purposes]:
        if term and term in text:
            score += 8
    for keyword in need.keywords:
        if keyword in text:
            score += 3

    if need.budget_cents and product.price_cents > 0:
        ratio = product.price_cents / need.budget_cents
        if ratio <= 1:
            score += 18
        elif ratio <= 1.2:
            score += 8
        elif ratio > 1.8:
            score -= 16
        else:
            score -= 6

    if candidate.merchant_tier == "vip":
        score += 5
    if product.updated_at:
        days = max(0, (datetime.now(UTC) - product.updated_at).days)
        score += max(0, 5 - min(days, 30) / 6)
    return score


def _product_text(product: MerchantProduct) -> str:
    params = product.match_params if isinstance(product.match_params, dict) else {}
    return " ".join(
        [
            product.title,
            product.summary,
            product.detail,
            product.search_text,
            " ".join(product.tags),
            " ".join(str(value) for value in params.values()),
        ]
    )


def _product_card(candidate: ProductCandidate) -> ProductCard:
    product = candidate.product
    return ProductCard.model_validate(
        {
            "id": str(product.id),
            "title": product.title,
            "tags": product.tags[:10],
            "priceCents": product.price_cents,
            "imageUrl": candidate.image_url,
            "merchantTier": candidate.merchant_tier,
        }
    )
