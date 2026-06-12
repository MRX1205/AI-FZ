from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "高翠网 API"
    environment: str = "local"
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    database_url: str = "postgresql+asyncpg://fz_user:fz_password@127.0.0.1:55432/fz"
    sync_database_url: str = "postgresql://fz_user:fz_password@127.0.0.1:55432/fz"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
