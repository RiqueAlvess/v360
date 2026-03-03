from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "VIVAMENTE 360º"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/vivamente360"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Security
    SECRET_KEY: str = Field(min_length=32)
    ENCRYPTION_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Email — Resend
    RESEND_API_KEY: str = Field(default="re_placeholder")
    EMAIL_FROM: str = "noreply@vivamente.com.br"
    EMAIL_FROM_NAME: str = "VIVAMENTE 360º"
    RESEND_WEBHOOK_SECRET: str = Field(default="whsec_placeholder")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "postgres")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
