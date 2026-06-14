from dataclasses import dataclass

import httpx

from app.core.config import settings


class ProductEmbeddingError(Exception):
    pass


@dataclass(frozen=True)
class EmbeddingResult:
    provider: str
    model: str
    dimensions: int
    embedding: list[float]


class DashScopeEmbeddingClient:
    provider = "dashscope"

    async def embed_document(self, text: str, timeout_seconds: float = 30) -> EmbeddingResult:
        if not settings.dashscope_api_key.strip():
            raise ProductEmbeddingError("DashScope API Key 未配置")
        if not text.strip():
            raise ProductEmbeddingError("商品匹配文本为空")

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    f"{settings.dashscope_base_url.rstrip('/')}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.dashscope_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.dashscope_embedding_model,
                        "input": text,
                        "dimensions": settings.dashscope_embedding_dimensions,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise ProductEmbeddingError("商品向量生成失败，请稍后重试") from error

        data = response.json()
        embedding = data.get("data", [{}])[0].get("embedding")
        if not isinstance(embedding, list):
            raise ProductEmbeddingError("商品向量返回格式错误")

        dimensions = settings.dashscope_embedding_dimensions
        vector = [float(item) for item in embedding]
        if len(vector) != dimensions:
            raise ProductEmbeddingError("商品向量维度不匹配")

        return EmbeddingResult(
            provider=self.provider,
            model=settings.dashscope_embedding_model,
            dimensions=dimensions,
            embedding=vector,
        )


embedding_client = DashScopeEmbeddingClient()
