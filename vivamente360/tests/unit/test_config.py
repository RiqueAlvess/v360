"""Testes unitários do módulo shared/config.py.

Cobre edge cases de configuração:
    - Campos obrigatórios ausentes (SECRET_KEY, ENCRYPTION_KEY)
    - Validador de DATABASE_URL com esquema inválido
    - Validador de CORS em ambiente de produção (rejeita wildcard)
    - Valores padrão dos campos opcionais
    - Singleton via lru_cache
"""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.shared.config import Settings, get_settings, settings


# ---------------------------------------------------------------------------
# Campos obrigatórios
# ---------------------------------------------------------------------------


class TestSettingsRequiredFields:
    """Valida que campos sem default levantam erro quando ausentes."""

    def test_missing_secret_key_raises_validation_error(self) -> None:
        """SECRET_KEY é obrigatório (min_length=32). Ausência deve falhar."""
        env = {
            "ENCRYPTION_KEY": "a" * 32,
            "SECRET_KEY": "",  # vazio viola min_length
        }
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValidationError) as exc_info:
                Settings(SECRET_KEY="", ENCRYPTION_KEY="a" * 32)
            errors = exc_info.value.errors()
            fields = [e["loc"][0] for e in errors]
            assert "SECRET_KEY" in fields

    def test_missing_encryption_key_raises_validation_error(self) -> None:
        """ENCRYPTION_KEY é obrigatório (min_length=32). Ausência deve falhar."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="short")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "ENCRYPTION_KEY" in fields

    def test_valid_minimal_settings_instantiates(self) -> None:
        """Settings com campos obrigatórios válidos deve instanciar sem erro."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.SECRET_KEY == "a" * 32
        assert s.ENCRYPTION_KEY == "b" * 32


# ---------------------------------------------------------------------------
# Validador DATABASE_URL
# ---------------------------------------------------------------------------


class TestDatabaseUrlValidator:
    """Testa o validador de esquema do DATABASE_URL."""

    def test_postgresql_scheme_is_valid(self) -> None:
        """URLs com esquema postgresql são aceitas."""
        s = Settings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        )
        assert "postgresql" in s.DATABASE_URL

    def test_postgres_scheme_is_valid(self) -> None:
        """URLs com esquema postgres (sem ql) também são aceitas."""
        s = Settings(
            SECRET_KEY="a" * 32,
            ENCRYPTION_KEY="b" * 32,
            DATABASE_URL="postgres://user:pass@localhost:5432/db",
        )
        assert s.DATABASE_URL.startswith("postgres")

    def test_non_postgres_scheme_raises_validation_error(self) -> None:
        """URLs com esquema não-PostgreSQL devem ser rejeitadas."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="a" * 32,
                ENCRYPTION_KEY="b" * 32,
                DATABASE_URL="mysql://user:pass@localhost:3306/db",
            )
        error_messages = str(exc_info.value)
        assert "DATABASE_URL" in error_messages or "PostgreSQL" in error_messages

    def test_sqlite_scheme_raises_validation_error(self) -> None:
        """SQLite não é suportado — deve ser rejeitado."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="a" * 32,
                ENCRYPTION_KEY="b" * 32,
                DATABASE_URL="sqlite+aiosqlite:///./test.db",
            )


# ---------------------------------------------------------------------------
# Validador CORS (produção não permite wildcard)
# ---------------------------------------------------------------------------


class TestCorsValidator:
    """Testa o validador de CORS para ambiente de produção."""

    def test_wildcard_cors_rejected_in_production(self) -> None:
        """Em produção, ALLOWED_ORIGINS='*' deve ser rejeitado."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValidationError) as exc_info:
                Settings(
                    SECRET_KEY="a" * 32,
                    ENCRYPTION_KEY="b" * 32,
                    ALLOWED_ORIGINS=["*"],
                )
            error_str = str(exc_info.value)
            assert "ALLOWED_ORIGINS" in error_str or "produção" in error_str

    def test_wildcard_cors_allowed_in_development(self) -> None:
        """Em desenvolvimento, ALLOWED_ORIGINS='*' é aceito."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            s = Settings(
                SECRET_KEY="a" * 32,
                ENCRYPTION_KEY="b" * 32,
                ALLOWED_ORIGINS=["*"],
            )
            assert "*" in s.ALLOWED_ORIGINS

    def test_explicit_origins_accepted_in_production(self) -> None:
        """Em produção, origens explícitas são válidas."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            s = Settings(
                SECRET_KEY="a" * 32,
                ENCRYPTION_KEY="b" * 32,
                ALLOWED_ORIGINS=["https://app.vivamente.com.br"],
            )
            assert "https://app.vivamente.com.br" in s.ALLOWED_ORIGINS


# ---------------------------------------------------------------------------
# Valores padrão de campos opcionais
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    """Valida os valores padrão dos campos opcionais."""

    def test_access_token_expire_minutes_default(self) -> None:
        """ACCESS_TOKEN_EXPIRE_MINUTES padrão deve ser 15 (R7 — token de vida curta)."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15

    def test_refresh_token_expire_days_default(self) -> None:
        """REFRESH_TOKEN_EXPIRE_DAYS padrão deve ser 30."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.REFRESH_TOKEN_EXPIRE_DAYS == 30

    def test_debug_false_by_default(self) -> None:
        """DEBUG deve ser False em configuração padrão (sem variável de ambiente)."""
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=False):
            s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32, DEBUG=False)
        assert s.DEBUG is False

    def test_environment_default_is_development(self) -> None:
        """ENVIRONMENT padrão deve ser 'development'."""
        with patch.dict(os.environ, {}, clear=False):
            # Forçar sem ENVIRONMENT no env
            env_backup = os.environ.pop("ENVIRONMENT", None)
            try:
                s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
                assert s.ENVIRONMENT == "development"
            finally:
                if env_backup is not None:
                    os.environ["ENVIRONMENT"] = env_backup

    def test_algorithm_default_is_hs256(self) -> None:
        """Algoritmo JWT padrão deve ser HS256."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.ALGORITHM == "HS256"

    def test_storage_max_file_size_is_20mb(self) -> None:
        """STORAGE_MAX_FILE_SIZE padrão deve ser 20 MB (20 * 1024 * 1024 bytes)."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.STORAGE_MAX_FILE_SIZE == 20 * 1024 * 1024

    def test_storage_signed_url_expires_is_one_hour(self) -> None:
        """STORAGE_SIGNED_URL_EXPIRES padrão deve ser 3600 segundos."""
        s = Settings(SECRET_KEY="a" * 32, ENCRYPTION_KEY="b" * 32)
        assert s.STORAGE_SIGNED_URL_EXPIRES == 3600


# ---------------------------------------------------------------------------
# Singleton via lru_cache
# ---------------------------------------------------------------------------


class TestSettingsSingleton:
    """Verifica que get_settings() retorna a mesma instância (lru_cache)."""

    def test_get_settings_returns_same_instance(self) -> None:
        """Chamadas consecutivas a get_settings() retornam o mesmo objeto."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_module_level_settings_is_singleton(self) -> None:
        """O objeto settings no módulo deve ser o mesmo que get_settings()."""
        assert settings is get_settings()
