from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCard(BaseModel):
    id: str
    title: str
    tags: list[str]
    price_cents: int = Field(validation_alias="priceCents", serialization_alias="priceCents")
    image_url: str = Field(validation_alias="imageUrl", serialization_alias="imageUrl")
    merchant_tier: str = Field(validation_alias="merchantTier", serialization_alias="merchantTier")

    model_config = ConfigDict(populate_by_name=True)


class VisitorNeedTagOut(BaseModel):
    name: str
    score: int


class VisitorNeedParamOut(BaseModel):
    category: str
    value: str


class VisitorNeedProfileOut(BaseModel):
    id: UUID
    source_type: str = Field(serialization_alias="sourceType")
    original_question: str = Field(serialization_alias="originalQuestion")
    normalized_question: str = Field(serialization_alias="normalizedQuestion")
    title: str
    summary: str
    detail: str
    tags: list[VisitorNeedTagOut]
    params: list[VisitorNeedParamOut]

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    need_profile: VisitorNeedProfileOut | None = Field(
        default=None,
        serialization_alias="needProfile",
    )
    matched_products: list[ProductCard] | None = Field(
        default=None,
        serialization_alias="matchedProducts",
    )
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class ChatSessionCreate(BaseModel):
    visitor_id: str = Field(min_length=1, max_length=128, validation_alias="visitorId")
    merchant_id: UUID | None = Field(default=None, validation_alias="merchantId")


class ChatSessionOut(BaseModel):
    session_id: UUID = Field(serialization_alias="sessionId")
    messages: list[ChatMessageOut]

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class ChatMessagePairOut(BaseModel):
    user_message: ChatMessageOut = Field(serialization_alias="userMessage")
    assistant_message: ChatMessageOut = Field(serialization_alias="assistantMessage")

    model_config = ConfigDict(populate_by_name=True)
