import base64
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import MerchantProduct
from app.services.jade_agent import MimoCompletionError, jade_agent
from app.services.product_search import (
    MATCH_PARAM_KEYS,
    normalize_match_params,
    refresh_product_search_text,
)

UPLOAD_BASE = Path(__file__).resolve().parents[2] / "uploads"

PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE = """你是高翠网商家端商品图片识别生成 Agent。
你的任务是专门识别商家上传的翡翠商品图片，并生成商品发布草稿。
你只根据图片中的可见信息输出，不凭空编造证书、尺寸、瑕疵、价格。
图片看不出来的字段统一写“未知”。
你不做真伪鉴定承诺，不输出“保真”“天然A货”等确定性结论，除非图片或商家资料明确提供。
你不负责发布商品、不负责游客匹配、不负责embedding。"""

PRODUCT_IMAGE_RECOGNITION_PROMPT = f"""{PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE}

请根据商家上传的翡翠图片生成商品发布初稿。
只返回JSON对象，不要使用Markdown代码块。
字段必须包含：title、summary、detail、tags、priceCents、matchParams。
title不超过10个中文字符，summary不超过50个中文字符，detail不超过300个中文字符，tags最多10个。
priceCents为AI预估售价，单位为人民币分，必须结合图片可见的品类、颜色、通透度、做工和常见市场区间给出合理参考价。
如果只能粗略判断，也要给中位参考价，常见手镯优先给30000-80000元区间内的参考价；只有完全无法判断品类或材质时才返回0。
matchParams必须包含：category、water、color、shape、size、flaw、purpose、certificate、visibleFeatures。
"""


@dataclass(frozen=True)
class ProductImageRecognitionResult:
    title: str
    summary: str
    detail: str
    tags: list[str]
    price_cents: int
    match_params: dict[str, str]


class ProductImageRecognitionError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProductImageRecognitionAgent:
    async def recognize_and_save_product(
        self,
        *,
        product: MerchantProduct,
        image_urls: list[str],
        db: AsyncSession,
    ) -> MerchantProduct:
        if not image_urls:
            raise ProductImageRecognitionError("请先上传商品图片", status_code=400)

        image_data_urls = [self._product_image_data_url(image_url) for image_url in image_urls[:6]]
        generated_fields = await self.generate_product_copy_from_images(image_data_urls)

        product.title = generated_fields.title
        product.summary = generated_fields.summary
        product.detail = generated_fields.detail
        product.tags = generated_fields.tags
        product.price_cents = generated_fields.price_cents
        product.match_params = generated_fields.match_params
        product.image_urls = image_urls
        refresh_product_search_text(product)

        await db.commit()
        await db.refresh(product)
        return product

    async def generate_product_copy_from_images(
        self,
        image_urls: list[str],
    ) -> ProductImageRecognitionResult:
        if not settings.mimo_api_key.strip():
            raise ProductImageRecognitionError("MiMo API Key 未配置")

        content: list[dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": image_url}}
            for image_url in image_urls[:6]
        ]
        content.append({"type": "text", "text": PRODUCT_IMAGE_RECOGNITION_PROMPT})

        last_error: ProductImageRecognitionError | None = None
        for attempt in range(2):
            prompt_content = content
            if attempt == 1:
                prompt_content = [
                    *content,
                    {
                        "type": "text",
                        "text": "上一次输出不是可解析JSON。请重新只返回一个JSON对象。",
                    },
                ]
            try:
                reply = await jade_agent.chat_completion(
                    [
                        {"role": "system", "content": PRODUCT_IMAGE_RECOGNITION_AGENT_ROLE},
                        {"role": "user", "content": prompt_content},
                    ],
                    raise_on_error=True,
                )
            except MimoCompletionError as error:
                raise ProductImageRecognitionError(str(error)) from error
            if not reply:
                raise ProductImageRecognitionError("AI服务未返回内容，请稍后重试")
            try:
                return self._parse_product_copy(reply)
            except ProductImageRecognitionError as error:
                last_error = error

        raise last_error or ProductImageRecognitionError("AI返回格式错误")

    def _parse_product_copy(self, reply: str) -> ProductImageRecognitionResult:
        try:
            raw = json.loads(self._extract_json(reply))
        except json.JSONDecodeError:
            raise ProductImageRecognitionError("AI返回格式错误") from None

        if not isinstance(raw, dict):
            raise ProductImageRecognitionError("AI返回格式错误")

        tags = raw.get("tags")
        price_cents = self._parse_price_cents(raw.get("priceCents") or raw.get("price_cents"))
        match_params = normalize_match_params(raw.get("matchParams") or raw.get("match_params"))
        result = ProductImageRecognitionResult(
            title=str(raw.get("title") or "").strip()[:10],
            summary=str(raw.get("summary") or "").strip()[:50],
            detail=str(raw.get("detail") or "").strip()[:300],
            tags=[str(tag).strip()[:20] for tag in tags if str(tag).strip()][:10]
            if isinstance(tags, list)
            else [],
            price_cents=price_cents,
            match_params=match_params,
        )
        if result.price_cents <= 0:
            result = ProductImageRecognitionResult(
                title=result.title,
                summary=result.summary,
                detail=result.detail,
                tags=result.tags,
                price_cents=self._fallback_price_cents(result),
                match_params=result.match_params,
            )
        if (
            not result.title
            or not result.summary
            or not result.detail
            or not result.tags
            or any(key not in result.match_params for key in MATCH_PARAM_KEYS)
        ):
            raise ProductImageRecognitionError("AI返回内容不完整")
        return result

    def _parse_price_cents(self, value: object) -> int:
        if isinstance(value, int):
            return max(value, 0)
        if isinstance(value, float):
            return max(round(value), 0)
        if isinstance(value, str):
            digits = re.sub(r"[^\d.]", "", value)
            if not digits:
                return 0
            try:
                amount = float(digits)
            except ValueError:
                return 0
            if "元" in value or "¥" in value or amount < 100_000:
                return max(round(amount * 100), 0)
            return max(round(amount), 0)
        return 0

    def _fallback_price_cents(self, result: ProductImageRecognitionResult) -> int:
        text = " ".join(
            [
                result.title,
                result.summary,
                result.detail,
                " ".join(result.tags),
                " ".join(result.match_params.values()),
            ]
        )
        if "手镯" in text or "镯" in text:
            return 48_000 * 100
        if "吊坠" in text or "挂件" in text:
            return 18_000 * 100
        if "戒" in text or "蛋面" in text:
            return 12_000 * 100
        if "珠" in text or "串" in text:
            return 8_000 * 100
        if "翡翠" in text or "玉" in text:
            return 6_800 * 100
        return 0

    def _extract_json(self, reply: str) -> str:
        text = reply.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1)
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text

    def _product_image_data_url(self, image_url: str) -> str:
        normalized_url = self._normalize_image_url(image_url)
        if not normalized_url.startswith("/uploads/"):
            raise ProductImageRecognitionError("请上传商品图片后再生成", status_code=400)

        relative_path = normalized_url.removeprefix("/uploads/")
        image_path = self._resolve_uploaded_image_path(relative_path)
        if not image_path.exists():
            raise ProductImageRecognitionError("商品图片不存在", status_code=400)

        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _normalize_image_url(self, image_url: str) -> str:
        parsed = urlparse(image_url)
        if parsed.scheme and parsed.netloc:
            return parsed.path
        return image_url.split("?", 1)[0]

    def _resolve_uploaded_image_path(self, relative_path: str) -> Path:
        candidates = [
            UPLOAD_BASE / relative_path,
            UPLOAD_BASE / "products" / relative_path,
        ]
        if relative_path.startswith("products/"):
            candidates.append(UPLOAD_BASE / relative_path.removeprefix("products/"))

        checked: set[Path] = set()
        for candidate in candidates:
            if candidate in checked:
                continue
            checked.add(candidate)
            if candidate.exists():
                return candidate
        return candidates[0]


product_image_recognition_agent = ProductImageRecognitionAgent()
