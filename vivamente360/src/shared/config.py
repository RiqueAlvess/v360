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

    # IA — OpenRouter (análise de sentimento e diagnóstico via LLM)
    OPENROUTER_API_KEY: str = Field(default="sk-or-placeholder")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    # Rate limit de análises IA por empresa por hora (Módulo 06)
    OPENROUTER_RATE_LIMIT_PER_HOUR: int = 10

    # SQLAdmin — painel global separado do JWT da aplicação
    SQLADMIN_SECRET_KEY: str = "change-this-sqladmin-secret"
    SQLADMIN_USERNAME: str = "superadmin"
    SQLADMIN_PASSWORD: str = "changeme"

    # Storage — Cloudflare R2 / S3-compatible
    STORAGE_BUCKET_NAME: str = Field(default="vivamente-files")
    STORAGE_ENDPOINT_URL: str = Field(default="https://placeholder.r2.cloudflarestorage.com")
    STORAGE_ACCESS_KEY_ID: str = Field(default="placeholder_access_key")
    STORAGE_SECRET_ACCESS_KEY: str = Field(default="placeholder_secret_key")
    STORAGE_REGION: str = Field(default="auto")
    # Expiração padrão das signed URLs em segundos (1 hora)
    STORAGE_SIGNED_URL_EXPIRES: int = 3600
    # Tamanho máximo de upload em bytes (20 MB)
    STORAGE_MAX_FILE_SIZE: int = 20 * 1024 * 1024

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "postgres")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: object) -> object:
        """Garante que CORS não expõe wildcard em produção."""
        import os

        if os.getenv("ENVIRONMENT", "development") == "production":
            origins = v if isinstance(v, list) else [v]
            for origin in origins:
                if str(origin).strip() == "*":
                    raise ValueError(
                        "ALLOWED_ORIGINS não pode ser '*' em produção. "
                        "Configure origens explícitas via variável de ambiente."
                    )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
