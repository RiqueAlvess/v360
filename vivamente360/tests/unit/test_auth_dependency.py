"""Testes unitários da dependência get_current_user (presentation/dependencies/auth.py).

Cobre todos os caminhos de erro e sucesso do decorador FastAPI:
    - Sem header Authorization → 401
    - Bearer malformado / JWT inválido → 401
    - Claims obrigatórios ausentes (sub, company_id, role) → 401
    - UUID em formato inválido → 401
    - Role desconhecida → 401
    - Token válido com todos os claims → CurrentUser com dados corretos
    - Context RLS configurado na sessão de banco via SET LOCAL
"""
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.shared.exceptions import UnauthorizedError


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------

FAKE_USER_ID: uuid.UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FAKE_COMPANY_ID: uuid.UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_credentials(token: str) -> MagicMock:
    """Simula HTTPAuthorizationCredentials com o token fornecido."""
    credentials = MagicMock()
    credentials.credentials = token
    return credentials


def _make_valid_token(
    user_id: uuid.UUID = FAKE_USER_ID,
    company_id: uuid.UUID = FAKE_COMPANY_ID,
    role: str = "admin",
) -> str:
    """Gera um JWT válido usando a função real de criação de tokens."""
    from src.shared.security import create_access_token

    return create_access_token(
        subject=str(user_id),
        company_id=str(company_id),
        role=role,
    )


@pytest.fixture
def mock_db() -> AsyncMock:
    """AsyncSession mockada para injeção na dependência."""
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Casos de erro — sem credenciais
# ---------------------------------------------------------------------------


class TestGetCurrentUserNoCredentials:
    async def test_no_credentials_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Ausência de header Authorization deve levantar UnauthorizedError."""
        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(credentials=None, db=mock_db)

        assert exc_info.value.status_code == 401

    async def test_no_credentials_error_message(self, mock_db: AsyncMock) -> None:
        """Mensagem de erro deve indicar ausência do token."""
        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(credentials=None, db=mock_db)

        assert "fornecido" in exc_info.value.detail.lower() or "token" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Casos de erro — JWT malformado/inválido
# ---------------------------------------------------------------------------


class TestGetCurrentUserInvalidToken:
    async def test_malformed_token_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Token JWT com assinatura inválida deve levantar UnauthorizedError."""
        credentials = _make_credentials("este.nao.e.um.jwt.valido")

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)

    async def test_random_string_as_token_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """String aleatória no lugar do token deve levantar UnauthorizedError."""
        credentials = _make_credentials("nao_sou_um_jwt")

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)

    async def test_expired_token_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Token expirado deve levantar UnauthorizedError."""
        from src.shared.security import create_access_token

        expired_token = create_access_token(
            subject=str(FAKE_USER_ID),
            company_id=str(FAKE_COMPANY_ID),
            role="admin",
            expires_delta=timedelta(seconds=-1),  # Já expirado
        )
        credentials = _make_credentials(expired_token)

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)


# ---------------------------------------------------------------------------
# Casos de erro — claims ausentes ou inválidos
# ---------------------------------------------------------------------------


class TestGetCurrentUserMissingClaims:
    async def test_token_without_sub_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Token sem claim 'sub' deve levantar UnauthorizedError."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            # sem "sub"
            "company_id": str(FAKE_COMPANY_ID),
            "role": "admin",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)

        assert "claims" in exc_info.value.detail.lower() or "inválido" in exc_info.value.detail.lower()

    async def test_token_without_company_id_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Token sem claim 'company_id' deve levantar UnauthorizedError."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            "sub": str(FAKE_USER_ID),
            # sem "company_id"
            "role": "admin",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)

    async def test_token_without_role_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Token sem claim 'role' deve levantar UnauthorizedError."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            "sub": str(FAKE_USER_ID),
            "company_id": str(FAKE_COMPANY_ID),
            # sem "role"
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)


# ---------------------------------------------------------------------------
# Casos de erro — formato inválido nos claims
# ---------------------------------------------------------------------------


class TestGetCurrentUserInvalidClaimFormat:
    async def test_invalid_uuid_for_user_id_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """UUID inválido no claim 'sub' deve levantar UnauthorizedError."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            "sub": "nao-e-um-uuid",  # UUID inválido
            "company_id": str(FAKE_COMPANY_ID),
            "role": "admin",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)

        assert "formato" in exc_info.value.detail.lower() or "inválido" in exc_info.value.detail.lower()

    async def test_invalid_uuid_for_company_id_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """UUID inválido no claim 'company_id' deve levantar UnauthorizedError."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            "sub": str(FAKE_USER_ID),
            "company_id": "nao-e-um-uuid",  # UUID inválido
            "role": "admin",
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)

    async def test_invalid_role_raises_unauthorized(self, mock_db: AsyncMock) -> None:
        """Role desconhecida deve levantar UnauthorizedError (UserRole enum rejeita o valor)."""
        from src.shared.config import settings
        from jose import jwt

        payload = {
            "sub": str(FAKE_USER_ID),
            "company_id": str(FAKE_COMPANY_ID),
            "role": "superuser",  # Não existe no enum UserRole
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
        credentials = _make_credentials(token)

        with pytest.raises(UnauthorizedError):
            await get_current_user(credentials=credentials, db=mock_db)


# ---------------------------------------------------------------------------
# Caso de sucesso
# ---------------------------------------------------------------------------


class TestGetCurrentUserSuccess:
    async def test_valid_token_returns_current_user(self, mock_db: AsyncMock) -> None:
        """Token válido deve retornar CurrentUser com dados corretos."""
        from src.domain.enums.user_role import UserRole

        token = _make_valid_token(role="admin")
        credentials = _make_credentials(token)

        result = await get_current_user(credentials=credentials, db=mock_db)

        assert isinstance(result, CurrentUser)
        assert result.user_id == FAKE_USER_ID
        assert result.company_id == FAKE_COMPANY_ID
        assert result.role == UserRole.ADMIN

    async def test_valid_token_manager_role(self, mock_db: AsyncMock) -> None:
        """Token com role 'manager' deve retornar CurrentUser com role MANAGER."""
        from src.domain.enums.user_role import UserRole

        token = _make_valid_token(role="manager")
        credentials = _make_credentials(token)

        result = await get_current_user(credentials=credentials, db=mock_db)

        assert result.role == UserRole.MANAGER

    async def test_valid_token_respondent_role(self, mock_db: AsyncMock) -> None:
        """Token com role 'respondent' deve retornar CurrentUser com role RESPONDENT."""
        from src.domain.enums.user_role import UserRole

        token = _make_valid_token(role="respondent")
        credentials = _make_credentials(token)

        result = await get_current_user(credentials=credentials, db=mock_db)

        assert result.role == UserRole.RESPONDENT

    async def test_valid_token_sets_rls_company_id(self, mock_db: AsyncMock) -> None:
        """Token válido deve configurar app.company_id na sessão PostgreSQL (RLS)."""
        token = _make_valid_token()
        credentials = _make_credentials(token)

        await get_current_user(credentials=credentials, db=mock_db)

        # Verificar que execute foi chamado duas vezes (company_id e user_id)
        assert mock_db.execute.call_count == 2

    async def test_valid_token_sets_rls_user_id(self, mock_db: AsyncMock) -> None:
        """Token válido deve configurar app.user_id na sessão PostgreSQL (RLS)."""
        token = _make_valid_token()
        credentials = _make_credentials(token)

        await get_current_user(credentials=credentials, db=mock_db)

        # Inspecionar as chamadas ao execute para confirmar SET LOCAL app.user_id
        calls_str = str(mock_db.execute.call_args_list)
        assert "user_id" in calls_str

    async def test_valid_token_sets_rls_both_values(self, mock_db: AsyncMock) -> None:
        """Token válido configura company_id e user_id via SET LOCAL (duas queries)."""
        token = _make_valid_token()
        credentials = _make_credentials(token)

        await get_current_user(credentials=credentials, db=mock_db)

        # Deve executar exatamente 2 SET LOCAL (company_id e user_id)
        assert mock_db.execute.await_count == 2
