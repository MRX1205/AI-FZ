import hashlib

from app.models.product import MerchantProduct

MATCH_PARAM_KEYS = [
    "category",
    "water",
    "color",
    "shape",
    "size",
    "flaw",
    "purpose",
    "certificate",
    "visibleFeatures",
]

MATCH_PARAM_LABELS = {
    "category": "品类",
    "water": "种水",
    "color": "颜色",
    "shape": "器型",
    "size": "尺寸",
    "flaw": "瑕疵",
    "purpose": "用途",
    "certificate": "证书",
    "visibleFeatures": "可见特征",
}

UNKNOWN_VALUE = "未知"


def normalize_match_params(value: object) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    params: dict[str, str] = {}
    for key in MATCH_PARAM_KEYS:
        text = str(raw.get(key) or "").strip()
        params[key] = text[:80] if text else UNKNOWN_VALUE
    return params


def build_product_search_text(
    *,
    title: str,
    summary: str,
    detail: str,
    tags: list[str],
    price_cents: int,
    match_params: dict[str, str],
) -> str:
    normalized_params = normalize_match_params(match_params)
    price_text = f"{price_cents // 100}元" if price_cents > 0 else "未知"
    tag_text = "、".join(tag for tag in tags if tag.strip()) or UNKNOWN_VALUE
    param_text = "\n".join(
        f"{MATCH_PARAM_LABELS[key]}：{normalized_params[key]}" for key in MATCH_PARAM_KEYS
    )
    return "\n".join(
        [
            f"商品标题：{title.strip()}",
            f"商品简介：{summary.strip()}",
            f"详情：{detail.strip()}",
            f"商品标签：{tag_text}",
            f"预估售价：{price_text}",
            param_text,
        ]
    ).strip()


def refresh_product_search_text(product: MerchantProduct) -> None:
    product.match_params = normalize_match_params(product.match_params)
    product.search_text = build_product_search_text(
        title=product.title,
        summary=product.summary,
        detail=product.detail,
        tags=product.tags,
        price_cents=product.price_cents,
        match_params=product.match_params,
    )


def product_search_content_hash(product: MerchantProduct) -> str:
    return hashlib.sha256(product.search_text.encode("utf-8")).hexdigest()
