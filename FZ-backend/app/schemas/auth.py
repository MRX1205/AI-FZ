from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Invalid email")
    return email


class AuthCodeCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AuthCodeOut(BaseModel):
    ok: bool
    expires_in: int = Field(serialization_alias="expiresIn")
    dev_code: str | None = Field(default=None, serialization_alias="devCode")

    model_config = ConfigDict(populate_by_name=True)


class AuthLoginCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return value.strip()


class MerchantOut(BaseModel):
    id: UUID
    email: str
    tier: str


class AuthLoginOut(BaseModel):
    token: str
    merchant: MerchantOut


class MerchantMeOut(MerchantOut):
    session_expires_at: datetime = Field(serialization_alias="sessionExpiresAt")

    model_config = ConfigDict(populate_by_name=True)
