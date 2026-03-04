"""Fixtures compartilhadas para os testes do VIVAMENTE 360°.

Estrutura:
    - async_session: sessão de banco em memória (SQLite async) para testes unitários
    - test_client: AsyncClient do FastAPI com dependências mockadas
    - fake_user: CurrentUser fictício para autenticação em testes
    - fake_company_id: UUID fixo para multi-tenant tests
"""
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Variáveis de ambiente necessárias para o Settings do projeto
os.environ.setdefault("SECRET_KEY", "test_secret_key_minimum_32_characters_long")
os.environ.setdefault("ENCRYPTION_KEY", "test_encryption_key_minimum_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/vivamente360")

# Importações depois de setar env vars
from src.shared.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# IDs fixos para facilitar assertions nos testes
# ---------------------------------------------------------------------------

FAKE_COMPANY_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FAKE_USER_ID: uuid.UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FAKE_CAMPAIGN_ID: uuid.UUID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FAKE_FILE_ID: uuid.UUID = uuid.UUID("44444444-4444-4444-4444-444444444444")


# ---------------------------------------------------------------------------
# Fixture: CurrentUser fake para injeção nos testes
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_current_user():
    """CurrentUser fictício com role ADMIN para testes de routers."""
    from src.domain.enums.user_role import UserRole
    from src.presentation.dependencies.auth import CurrentUser

    return CurrentUser(
        user_id=FAKE_USER_ID,
        company_id=FAKE_COMPANY_ID,
        role=UserRole.ADMIN,
    )


@pytest.fixture
def fake_manager_user():
    """CurrentUser fictício com role MANAGER."""
    from src.domain.enums.user_role import UserRole
    from src.presentation.dependencies.auth import CurrentUser

    return CurrentUser(
        user_id=FAKE_USER_ID,
        company_id=FAKE_COMPANY_ID,
        role=UserRole.MANAGER,
    )


@pytest.fixture
def fake_respondent_user():
    """CurrentUser fictício com role RESPONDENT."""
    from src.domain.enums.user_role import UserRole
    from src.presentation.dependencies.auth import CurrentUser

    return CurrentUser(
        user_id=FAKE_USER_ID,
        company_id=FAKE_COMPANY_ID,
        role=UserRole.RESPONDENT,
    )


# ---------------------------------------------------------------------------
# Fixture: Mock de AsyncSession para testes unitários
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """AsyncSession mockada para testes unitários de serviços e repositórios."""
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Fixture: Mock de UserRepository para AuthService
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user_repo():
    """Mock de UserRepository."""
    from src.infrastructure.repositories.user_repository import UserRepository

    repo = AsyncMock(spec=UserRepository)
    return repo


@pytest.fixture
def mock_token_repo():
    """Mock de TokenRepository."""
    from src.infrastructure.repositories.token_repository import TokenRepository

    repo = AsyncMock(spec=TokenRepository)
    return repo


@pytest.fixture
def mock_campaign_repo():
    """Mock de CampaignRepository."""
    from src.infrastructure.repositories.campaign_repository import CampaignRepository

    repo = AsyncMock(spec=CampaignRepository)
    return repo


@pytest.fixture
def mock_checklist_repo():
    """Mock de ChecklistRepository."""
    from src.infrastructure.repositories.checklist_repository import ChecklistRepository

    repo = AsyncMock(spec=ChecklistRepository)
    return repo


@pytest.fixture
def mock_notification_repo():
    """Mock de NotificationRepository."""
    from src.infrastructure.repositories.notification_repository import NotificationRepository

    repo = AsyncMock(spec=NotificationRepository)
    return repo


@pytest.fixture
def mock_email_log_repo():
    """Mock de EmailLogRepository."""
    from src.infrastructure.repositories.email_log_repository import EmailLogRepository

    repo = AsyncMock(spec=EmailLogRepository)
    return repo


@pytest.fixture
def mock_storage_adapter():
    """Mock de StorageAdapter para testes de upload."""
    from src.infrastructure.storage.r2_adapter import StorageAdapter

    adapter = AsyncMock(spec=StorageAdapter)
    adapter.upload = AsyncMock(return_value="company/checklist/uuid/file.pdf")
    adapter.get_signed_url = AsyncMock(return_value="https://cdn.example.com/signed-url?token=abc")
    adapter.delete = AsyncMock(return_value=None)
    return adapter


# ---------------------------------------------------------------------------
# Fixture: FastAPI test client com autenticação mockada
# ---------------------------------------------------------------------------


@pytest.fixture
def test_app(fake_current_user, mock_session, mock_storage_adapter):
    """App FastAPI com dependências críticas substituídas por mocks."""
    from src.infrastructure.database.session import get_db
    from src.infrastructure.storage.r2_adapter import get_storage_adapter
    from src.main import app
    from src.presentation.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_adapter] = lambda: mock_storage_adapter

    yield app

    # Cleanup: remover overrides para não afetar outros testes
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient para testes de routers/endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_access_token(
    user_id: uuid.UUID = FAKE_USER_ID,
    company_id: uuid.UUID = FAKE_COMPANY_ID,
    role: str = "admin",
) -> str:
    """Gera um JWT de acesso válido para uso em testes de integração."""
    from src.shared.security import create_access_token

    return create_access_token(
        subject=str(user_id),
        company_id=str(company_id),
        role=role,
    )


def hash_token(value: str) -> str:
    """SHA-256 do valor — mesmo padrão do security.py."""
    return hashlib.sha256(value.encode()).hexdigest()
