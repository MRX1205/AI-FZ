import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import VisitorNeedProfile
from app.models.merchant import Merchant, MerchantTier
from app.models.product import MerchantProduct, MerchantProductEmbedding, MerchantProductImage
from app.schemas.chat import ProductCard
from app.services.embeddings import ProductEmbeddingError, embedding_client
from app.services.jade_agent import MimoCompletionError, jade_agent

MAX_MATCHES = 3
VECTOR_CANDIDATE_LIMIT = 50
RULE_CANDIDATE_LIMIT = 80
QUERY_EMBEDDING_CACHE: dict[str, list[float]] = {}
DEFAULT_REWRITTEN_QUESTION = "预算不限，适合日常佩戴或送礼的翡翠饰品"
ASSISTANT_GREETING = "您好！我是高翠AI，很高兴为您服务。"

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
CERTIFICATE_TERMS = ["证书", "有证书", "国检", "鉴定证书", "A货", "a货"]
STYLE_TERMS = ["简约", "古典", "国风", "精致", "大气", "高级", "清新", "优雅"]
NEED_INTENT_TERMS = [
    "找",
    "想要",
    "需要",
    "有没有",
    "推荐",
    "匹配",
    "预算",
    "买",
    "要",
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

PARAM_CATEGORIES = [
    "产品品类",
    "核心卖点",
    "主石材质",
    "翡翠造型",
    "翡翠种水",
    "翡翠颜色",
    "配石材质",
    "镶嵌工艺",
    "瑕疵情况",
    "款式风格",
    "适用场景",
    "产品寓意",
    "镶嵌材质",
    "镶嵌配件",
    "尺寸规格",
]

MEANING_BY_CATEGORY = {
    "手镯": "圆满吉祥",
    "吊坠": "护佑平安",
    "平安扣": "平安顺遂",
    "戒面": "精致贵气",
    "珠串": "圆融如意",
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
class NeedProfileData:
    source_type: str
    original_question: str
    normalized_question: str
    title: str
    summary: str
    detail: str
    tags: list[dict[str, int | str]]
    params: list[dict[str, str]]
    search_text: str


@dataclass(frozen=True)
class RewrittenNeed:
    normalized_question: str


@dataclass(frozen=True)
class MatchResult:
    content: str
    products: list[ProductCard]
    need_profile: VisitorNeedProfile | None = None


@dataclass(frozen=True)
class ProductCandidate:
    product: MerchantProduct
    merchant_tier: str
    image_url: str
    vector_distance: float | None


class VisitorNeedRewriteAgent:
    async def rewrite(self, content: str) -> RewrittenNeed:
        if not settings.mimo_api_key.strip():
            return RewrittenNeed(normalized_question=DEFAULT_REWRITTEN_QUESTION)

        prompt = (
            "你是高翠网游客需求改写 Agent。"
            "请把用户输入改写成一个翡翠购物需求问题。"
            "不要拒绝，不要解释，不要说无法帮助。"
            "即使问题与购物无关，也要联想到送礼、日常佩戴、收藏或预算场景。"
            "只输出JSON，格式为：{\"normalizedQuestion\":\"80字以内的翡翠购物需求\"}。"
        )
        try:
            rewritten = await jade_agent.chat_completion(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content.strip()[:300]},
                ],
                raise_on_error=True,
            )
        except MimoCompletionError:
            return RewrittenNeed(normalized_question=DEFAULT_REWRITTEN_QUESTION)

        cleaned = _clean_rewritten_question(_json_text_value(rewritten, "normalizedQuestion"))
        return RewrittenNeed(normalized_question=cleaned or DEFAULT_REWRITTEN_QUESTION)


class VisitorNeedVisibleReplyAgent:
    async def generate(
        self,
        *,
        original_question: str,
        normalized_question: str,
        source_type: str,
        need: VisitorNeed,
        has_products: bool,
        used_fallback: bool,
    ) -> str:
        fallback = _fallback_visible_content(
            source_type=source_type,
            original_question=original_question,
            need=need,
            has_products=has_products,
            used_fallback=used_fallback,
        )
        if not settings.mimo_api_key.strip():
            return fallback

        product_state = "下面会展示商品卡片" if has_products else "暂时没有合适商品卡片"
        match_hint = (
            "可以引导用户点开卡片查看"
            if has_products
            else "可以引导用户补充预算、品类或尺寸"
        )
        prompt = (
            "你是高翠AI，专业翡翠找货助手。"
            "请根据用户原始输入，写一段最终展示给游客看的聊天回复。"
            "回复必须是定制化的：结合用户话题自然联想到翡翠购物场景，"
            "例如送礼、日常佩戴、收藏、穿搭、预算选择或寓意。"
            "不要拒绝，不要说无法帮助。不要输出改写过程、结构化参数、"
            "标签表、参数表、匹配规则或思考过程。"
            "开头必须是“您好！我是高翠AI，很高兴为您服务。”。"
            "80到160个中文字符，不承诺鉴定或保真。"
            "只输出JSON，格式为：{\"reply\":\"最终给用户看的回复\"}。"
        )
        user_content = "\n".join(
            [
                f"用户原始输入：{original_question}",
                f"可参考的翡翠选购场景：{normalized_question}",
                f"用户是否原本就在找翡翠：{'是' if source_type == 'direct' else '否'}",
                f"预算参考：{_budget_text(need.budget_cents)}",
                f"品类参考：{need.category or '未限定'}",
                f"推荐结果状态：{product_state}",
                f"回复收尾方向：{match_hint}",
            ]
        )
        try:
            reply = await jade_agent.chat_completion(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
                raise_on_error=True,
            )
        except MimoCompletionError:
            return fallback

        cleaned = _clean_visible_reply(_json_text_value(reply, "reply"))
        return cleaned or fallback


class ProductMatchAgent:
    async def match(
        self,
        *,
        session_id: UUID,
        content: str,
        db: AsyncSession,
    ) -> MatchResult:
        original_question = re.sub(r"\s+", " ", content.strip())[:1000]
        is_direct = looks_like_product_need(original_question)
        normalized_question = original_question
        source_type = "direct"
        if not is_direct:
            rewritten = await visitor_need_rewrite_agent.rewrite(original_question)
            normalized_question = rewritten.normalized_question
            source_type = "rewritten"

        need = parse_visitor_need(normalized_question)
        profile_data = build_need_profile(
            source_type=source_type,
            original_question=original_question,
            normalized_question=normalized_question,
            need=need,
        )
        need = replace(need, search_text=profile_data.search_text)

        profile = VisitorNeedProfile(
            session_id=session_id,
            source_type=profile_data.source_type,
            original_question=profile_data.original_question,
            normalized_question=profile_data.normalized_question,
            title=profile_data.title,
            summary=profile_data.summary,
            detail=profile_data.detail,
            tags=profile_data.tags,
            params=profile_data.params,
            search_text=profile_data.search_text,
        )
        db.add(profile)
        await db.flush()

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

        content_text = await visitor_need_visible_reply_agent.generate(
            source_type=source_type,
            original_question=original_question,
            normalized_question=normalized_question,
            need=need,
            has_products=bool(products),
            used_fallback=used_fallback,
        )
        return MatchResult(content=content_text, products=products, need_profile=profile)


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
    has_jade_word = any(term in text for term in ["翡翠", "A货", "a货"])
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
    if has_jade_word and (has_feature or has_intent or need.budget_cents):
        return True
    return False


async def match_products_for_need(content: str, db: AsyncSession) -> MatchResult:
    return await _legacy_match_products_for_need(content, db)


async def match_products_for_session(
    *,
    session_id: UUID,
    content: str,
    db: AsyncSession,
) -> MatchResult:
    return await product_match_agent.match(session_id=session_id, content=content, db=db)


async def _legacy_match_products_for_need(content: str, db: AsyncSession) -> MatchResult:
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


def build_need_profile(
    *,
    source_type: str,
    original_question: str,
    normalized_question: str,
    need: VisitorNeed,
) -> NeedProfileData:
    title = _profile_title(need)
    summary = _truncate(_profile_summary(need), 50)
    detail = _truncate(_profile_detail(original_question, normalized_question, need), 300)
    tags = _profile_tags(need)
    params = _profile_params(need)
    search_text = _profile_search_text(
        title=title,
        summary=summary,
        detail=detail,
        tags=tags,
        params=params,
        budget_cents=need.budget_cents,
        normalized_question=normalized_question,
    )
    return NeedProfileData(
        source_type=source_type,
        original_question=original_question,
        normalized_question=normalized_question,
        title=title,
        summary=summary,
        detail=detail,
        tags=tags,
        params=params,
        search_text=search_text,
    )


def _clean_rewritten_question(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip().strip("\"'“”‘’"))
    text = re.sub(r"^(改写后[:：]?|需求[:：]?)", "", text).strip()
    return text[:80]


def _clean_visible_reply(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip().strip("\"'“”‘’"))
    blocked = [
        "产品品类",
        "匹配标签",
        "参数类别",
        "normalizedQuestion",
        "内部",
        "改写",
        "匹配规则",
        "思考过程",
        "标签\t匹配度",
    ]
    if any(item in text for item in blocked):
        return ""
    if not text.startswith(ASSISTANT_GREETING):
        text = f"{ASSISTANT_GREETING}{text}"
    return text[:220]


def _json_text_value(raw_text: str, key: str) -> str:
    text = raw_text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except ValueError:
        return raw_text
    value = data.get(key) if isinstance(data, dict) else None
    return str(value or raw_text)


def _profile_title(need: VisitorNeed) -> str:
    category = need.category or "翡翠饰品"
    prefix = _first_value([*need.colors, *need.waters, *need.purposes]) or "精选"
    return _truncate(f"{prefix}{category}", 15)


def _profile_summary(need: VisitorNeed) -> str:
    category = need.category or "翡翠饰品"
    budget = _budget_text(need.budget_cents)
    features = _join_or_unknown([*need.colors, *need.waters, *need.flaws])
    purpose = _join_or_unknown(need.purposes) if need.purposes else "日常佩戴或送礼"
    return f"{budget}，寻找{features}的{category}，适合{purpose}。"


def _profile_detail(
    original_question: str,
    normalized_question: str,
    need: VisitorNeed,
) -> str:
    category = need.category or "翡翠饰品"
    budget = _budget_text(need.budget_cents)
    features = _join_or_unknown([*need.colors, *need.waters, *need.flaws])
    purpose = _join_or_unknown(need.purposes) if need.purposes else "日常佩戴、送礼或收藏"
    size = _extract_size(normalized_question) or "未知"
    certificate = _join_or_unknown(need.certificates) if need.certificates else "不限"
    opening = (
        f"根据您输入的「{original_question}」，我已从翡翠选购角度整理出本次需求。"
        if original_question != normalized_question
        else f"根据您输入的「{original_question}」，我已整理出本次翡翠选购需求。"
    )
    return (
        opening +
        f"本次优先匹配{category}，预算为{budget}，重点关注{features}等特征，"
        f"适用场景为{purpose}。尺寸规格为{size}，证书要求为{certificate}。"
        "匹配时会优先考虑已上架商品、标签和参数命中、价格接近度、商家等级与更新时间。"
        "翡翠图片和描述仅供选货参考，最终以商家实物和补充信息为准。"
    )


def _fallback_visible_content(
    *,
    source_type: str,
    original_question: str,
    need: VisitorNeed,
    has_products: bool,
    used_fallback: bool,
) -> str:
    scenario = _assistant_scenario_sentence(original_question, need)
    if not has_products:
        result = (
            "我先按这个选购场景帮您找了一轮，暂时没有特别合适的货源。"
            "您可以再补充预算、品类或尺寸，我会继续帮您筛选。"
        )
    elif used_fallback:
        result = "我先按这个选购场景为您推荐几件相近货源，您可以点开看看。"
    else:
        result = "我按这个选购场景为您匹配到几件相近货源，您可以点开看看。"

    if source_type == "rewritten":
        return f"{ASSISTANT_GREETING}\n\n{scenario}{result}"
    return f"{ASSISTANT_GREETING}\n\n我已根据您的翡翠需求为您筛选。{result}"


def _assistant_scenario_sentence(original_question: str, need: VisitorNeed) -> str:
    if "生日" in original_question or "送礼" in need.purposes:
        return (
            "如果是送礼，可以优先看寓意好、佩戴门槛低的翡翠款式，"
            "比如平安扣、吊坠或清爽耐看的小件。"
        )
    if any(term in original_question for term in ["穿搭", "搭配", "上班", "日常"]):
        return (
            "如果是日常搭配，可以优先看清爽耐看、尺寸轻巧的翡翠饰品，"
            "比如冰种吊坠、平安扣或小精品手串。"
        )
    if "收藏" in need.purposes or "收藏" in original_question:
        return (
            "如果偏收藏，可以优先看种水、颜色和完整度更稳定的翡翠，"
            "预算允许时再关注稀缺色和精品器型。"
        )
    if any(term in original_question for term in ["结婚", "婚嫁", "纪念"]):
        return "如果是婚嫁或纪念场景，可以优先看寓意圆满、质感稳重的翡翠手镯、平安扣或成套饰品。"
    return "如果您刚开始了解翡翠，可以先从日常佩戴或送礼都稳妥的款式看起，比如平安扣、吊坠或手镯。"


def _profile_tags(need: VisitorNeed) -> list[dict[str, int | str]]:
    preferred = [
        need.category or "",
        *need.colors,
        *need.waters,
        *need.flaws,
        *need.purposes,
        *need.certificates,
        *_matched_terms(need.raw_text, STYLE_TERMS),
    ]
    fallback = [
        "翡翠",
        "预算匹配",
        "天然感",
        "细腻",
        "清爽",
        "经典",
        "送礼",
        "日常佩戴",
        "性价比",
        "可出证优先",
    ]
    names: list[str] = []
    for name in [*preferred, *fallback]:
        clean_name = name.strip()
        if clean_name and clean_name not in names:
            names.append(clean_name)
        if len(names) == 10:
            break
    return [
        {"name": name, "score": max(60, 98 - index * 4)}
        for index, name in enumerate(names[:10])
    ]


def _profile_params(need: VisitorNeed) -> list[dict[str, str]]:
    category = need.category or "不限"
    shape = _join_or_unknown(need.shapes) if need.shapes else category
    purpose = _join_or_unknown(need.purposes) if need.purposes else "日常佩戴、送礼"
    has_inlay_category = need.category in {"吊坠", "戒面"}
    values = {
        "产品品类": category,
        "核心卖点": _core_selling_point(need),
        "主石材质": "翡翠",
        "翡翠造型": shape,
        "翡翠种水": _join_or_unlimited(need.waters),
        "翡翠颜色": _join_or_unlimited(need.colors),
        "配石材质": "不限",
        "镶嵌工艺": "可接受简约镶嵌" if has_inlay_category else "不限",
        "瑕疵情况": _join_or_unknown(need.flaws),
        "款式风格": _style_value(need),
        "适用场景": purpose,
        "产品寓意": MEANING_BY_CATEGORY.get(need.category or "", "美好祝福"),
        "镶嵌材质": "18K金/银均可" if has_inlay_category else "不限",
        "镶嵌配件": "证书、包装可优先" if need.certificates else "不限",
        "尺寸规格": _extract_size(need.raw_text) or "未知",
    }
    return [
        {"category": category_name, "value": values[category_name]}
        for category_name in PARAM_CATEGORIES
    ]


def _profile_search_text(
    *,
    title: str,
    summary: str,
    detail: str,
    tags: list[dict[str, int | str]],
    params: list[dict[str, str]],
    budget_cents: int | None,
    normalized_question: str,
) -> str:
    tag_text = "、".join(str(tag["name"]) for tag in tags)
    param_text = "\n".join(f"{item['category']}：{item['value']}" for item in params)
    return "\n".join(
        [
            f"需求：{normalized_question}",
            f"需求标题：{title}",
            f"需求简介：{summary}",
            f"需求详情：{detail}",
            f"预算：{_budget_text(budget_cents)}",
            f"匹配标签：{tag_text}",
            param_text,
        ]
    )


def _core_selling_point(need: VisitorNeed) -> str:
    values = [*need.colors, *need.waters, *need.flaws, *need.purposes]
    if values:
        return "、".join(values[:4])
    return "适合日常佩戴或送礼"


def _style_value(need: VisitorNeed) -> str:
    styles = _matched_terms(need.raw_text, STYLE_TERMS)
    if styles:
        return "、".join(styles)
    if "送礼" in need.purposes:
        return "礼赠大方"
    if "收藏" in need.purposes:
        return "收藏雅致"
    return "经典耐看"


def _extract_size(text: str) -> str | None:
    match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*(圈口|mm|毫米|厘米|cm)", text, re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1)}{match.group(2)}"


def _budget_text(budget_cents: int | None) -> str:
    return f"{budget_cents // 100}元" if budget_cents else "不限"


def _join_or_unlimited(values: list[str]) -> str:
    return "、".join(values) if values else "不限"


def _first_value(values: list[str]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _truncate(value: str, max_length: int) -> str:
    text = value.strip()
    return text[:max_length]


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


visitor_need_rewrite_agent = VisitorNeedRewriteAgent()
visitor_need_visible_reply_agent = VisitorNeedVisibleReplyAgent()
product_match_agent = ProductMatchAgent()
