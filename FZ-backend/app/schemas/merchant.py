from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import normalize_email


class DashboardMerchantOut(BaseModel):
    id: UUID
    email: str
    tier: str


class DashboardStatsOut(BaseModel):
    listed_products: int = Field(serialization_alias="listedProducts")
    product_limit: int = Field(serialization_alias="productLimit")
    today_leads: int = Field(serialization_alias="todayLeads")
    total_leads: int = Field(serialization_alias="totalLeads")

    model_config = ConfigDict(populate_by_name=True)


class DashboardLeadOut(BaseModel):
    id: str
    submitted_at: datetime = Field(serialization_alias="submittedAt")
    buyer_email: str = Field(serialization_alias="buyerEmail")
    message: str
    product_title: str = Field(serialization_alias="productTitle")

    model_config = ConfigDict(populate_by_name=True)


class MerchantDashboardOut(BaseModel):
    merchant: DashboardMerchantOut
    stats: DashboardStatsOut
    recent_leads: list[DashboardLeadOut] = Field(serialization_alias="recentLeads")

    model_config = ConfigDict(populate_by_name=True)


class NotificationSettingsOut(BaseModel):
    web_notification_enabled: bool = Field(serialization_alias="webNotificationEnabled")
    email_notification_enabled: bool = Field(serialization_alias="emailNotificationEnabled")

    model_config = ConfigDict(populate_by_name=True)


class MerchantProfileOut(BaseModel):
    id: UUID
    email: str
    tier: str
    vip_started_at: datetime | None = Field(default=None, serialization_alias="vipStartedAt")
    vip_expires_at: datetime | None = Field(default=None, serialization_alias="vipExpiresAt")
    notifications: NotificationSettingsOut

    model_config = ConfigDict(populate_by_name=True)


class MerchantEmailCodeCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class MerchantEmailUpdate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=4, max_length=16)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return value.strip()


class MerchantNotificationUpdate(BaseModel):
    email_notification_enabled: bool = Field(validation_alias="emailNotificationEnabled")

    model_config = ConfigDict(populate_by_name=True)


class MerchantLeadOut(BaseModel):
    id: UUID
    submitted_at: datetime = Field(serialization_alias="submittedAt")
    buyer_email: str = Field(serialization_alias="buyerEmail")
    message: str
    product_title: str = Field(serialization_alias="productTitle")
    product_price_cents: int = Field(serialization_alias="productPriceCents")
    product_image_url: str = Field(serialization_alias="productImageUrl")
    status: str
    merchant_email: str = Field(serialization_alias="merchantEmail")

    model_config = ConfigDict(populate_by_name=True)


class MerchantLeadListOut(BaseModel):
    merchant: DashboardMerchantOut
    leads: list[MerchantLeadOut]


class MerchantLeadStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|contacted)$")


class MerchantNotificationOut(BaseModel):
    id: UUID
    type: str
    content: str
    sent_at: datetime = Field(serialization_alias="sentAt")

    model_config = ConfigDict(populate_by_name=True)


class MerchantNotificationListOut(BaseModel):
    merchant: DashboardMerchantOut
    notifications: list[MerchantNotificationOut]


class MerchantProductOut(BaseModel):
    id: UUID
    title: str
    summary: str
    detail: str
    tags: list[str]
    price_cents: int = Field(serialization_alias="priceCents")
    status: str
    image_urls: list[str] = Field(serialization_alias="imageUrls")
    published_at: datetime | None = Field(default=None, serialization_alias="publishedAt")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class MerchantProductCountsOut(BaseModel):
    all: int
    listed: int
    draft: int
    unlisted: int


class MerchantProductQuotaOut(BaseModel):
    listed_count: int = Field(serialization_alias="listedCount")
    product_limit: int = Field(serialization_alias="productLimit")
    remaining: int

    model_config = ConfigDict(populate_by_name=True)


class MerchantProductListOut(BaseModel):
    merchant: DashboardMerchantOut
    products: list[MerchantProductOut]
    counts: MerchantProductCountsOut
    quota: MerchantProductQuotaOut


class MerchantProductUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=1200)
    tags: list[str] = Field(default_factory=list, max_length=10)
    price_cents: int = Field(validation_alias="priceCents", ge=1)

    @field_validator("title", "summary", "detail")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        tags: list[str] = []
        for tag in value:
            clean_tag = tag.strip()
            if clean_tag and clean_tag not in tags:
                tags.append(clean_tag[:20])
        return tags[:10]

    model_config = ConfigDict(populate_by_name=True)


class MerchantProductStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|listed|unlisted)$")
