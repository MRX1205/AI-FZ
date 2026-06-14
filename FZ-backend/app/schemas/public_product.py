from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import normalize_email


class PublicProductOut(BaseModel):
    id: UUID
    title: str
    summary: str
    detail: str
    tags: list[str]
    price_cents: int = Field(serialization_alias="priceCents")
    image_urls: list[str] = Field(serialization_alias="imageUrls")
    merchant_tier: str = Field(serialization_alias="merchantTier")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class PublicProductContactCreate(BaseModel):
    buyer_email: str = Field(min_length=3, max_length=320, validation_alias="buyerEmail")

    @field_validator("buyer_email")
    @classmethod
    def validate_buyer_email(cls, value: str) -> str:
        return normalize_email(value)

    model_config = ConfigDict(populate_by_name=True)


class PublicProductContactOut(BaseModel):
    ok: bool
    message: str
    lead_id: UUID | None = Field(default=None, serialization_alias="leadId")

    model_config = ConfigDict(populate_by_name=True)
