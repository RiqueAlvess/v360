"""Configurações centralizadas da aplicação via pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do ambiente / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Aplicação ────────────────────────────────────────────────────────────
    APP_NAME: str = "VIVAMENTE 360º"
    APP_VERSION: str = "1.0.0"
    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Banco de Dados ────────────────────────────────────────────────────────
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/vivamente360",
        description="URL de conexão ao PostgreSQL (asyncpg driver)",
    )

    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    # ── Segurança / JWT ───────────────────────────────────────────────────────
    SECRET_KEY: str = Field(
        ...,
        description="Chave secreta para assinatura de JWT (mínimo 32 chars)",
        min_length=32,
    )
    ENCRYPTION_KEY: str = Field(
        ...,
        description="Chave de criptografia simétrica para dados sensíveis (32 bytes hex)",
    )

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Email ─────────────────────────────────────────────────────────────────
    RESEND_API_KEY: str = Field(
        ...,
        description="API Key do Resend para envio de emails",
    )
    EMAIL_FROM: str = "noreply@vivamente360.com.br"
    EMAIL_FROM_NAME: str = "VIVAMENTE 360º"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # ── Admin ─────────────────────────────────────────────────────────────────
    ADMIN_SECRET_KEY: str = Field(
        default="",
        description="Chave para sessão do SQLAdmin (herda SECRET_KEY se vazio)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def effective_admin_secret_key(self) -> str:
        """Retorna a chave do admin, usando SECRET_KEY como fallback."""
        return self.ADMIN_SECRET_KEY or self.SECRET_KEY

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância singleton das configurações (cacheada)."""
    return Settings()  # type: ignore[call-arg]


# Instância global para import direto
settings: Settings = get_settings()
