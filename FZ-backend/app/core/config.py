from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "高翠网 API"
    environment: str = "local"
    backend_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    database_url: str
    sync_database_url: str
    redis_url: str
    secret_key: str
    mimo_api_key: str = ""
    mimo_base_url: str = "https://api.xiaomimimo.com/v1"
    mimo_model: str = "mimo-v2.5"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_embedding_model: str = "text-embedding-v4"
    dashscope_embedding_dimensions: int = 1024
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_otp_expires_seconds: int = 300
    supabase_auth_timeout_seconds: float = 10.0
    supabase_email_redirect_to: str = ""
    alipay_app_id: str = ""
    alipay_gateway_url: str = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
    alipay_app_private_key_path: str = ""
    alipay_alipay_public_key_path: str = ""
    alipay_seller_id: str = ""
    alipay_notify_url: str = ""
    alipay_return_url: str = ""
    alipay_timeout_express: str = "15m"
    frontend_public_base_url: str = ""
    backend_public_base_url: str = ""

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_backend_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env.bak.codex",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
