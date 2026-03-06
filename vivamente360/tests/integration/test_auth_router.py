"""Testes de integração do auth_router.

Testa os endpoints HTTP diretamente via AsyncClient:
    - POST /api/v1/auth/login
    - POST /api/v1/auth/refresh
    - POST /api/v1/auth/logout
    - POST /api/v1/auth/admin/schedule-token-cleanup

Os testes mockam as dependências de banco e autenticação para execução
sem infraestrutura real.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _make_fake_user():
    user = MagicMock()
    user.id = USER_ID
    user.company_id = COMPANY_ID
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = True
    user.verify_password = MagicMock(return_value=True)
    return user


def _make_fake_token():
    token = MagicMock()
    token.id = uuid.uuid4()
    token.user_id = USER_ID
    token.revogado = False
    return token


@pytest.fixture
def auth_test_app(mock_session):
    """App com sessão mockada mas sem override de autenticação."""
    from src.infrastructure.database.session import get_db
    from src.main import app

    app.dependency_overrides[get_db] = lambda: mock_session

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(auth_test_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=auth_test_app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    async def test_login_success_returns_200_with_tokens(self, auth_client, mock_session):
        """Login válido retorna HTTP 200 com access_token e refresh_token."""
        fake_user = _make_fake_user()
        fake_token = _make_fake_token()

        with (
            patch(
                "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_email_hash",
                new=AsyncMock(return_value=fake_user),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.create",
                new=AsyncMock(return_value=fake_token),
            ),
        ):
            response = await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "senha_correta"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials_returns_401(self, auth_client):
        """Login com credenciais inválidas retorna HTTP 401."""
        with patch(
            "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_email_hash",
            new=AsyncMock(return_value=None),
        ):
            response = await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "unknown@example.com", "password": "errado"},
            )

        assert response.status_code == 401

    async def test_login_missing_fields_returns_422(self, auth_client):
        """Login sem campos obrigatórios retorna HTTP 422."""
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com"},  # Sem password
        )

        assert response.status_code == 422

    async def test_login_wrong_password_returns_401(self, auth_client):
        """Login com senha incorreta retorna HTTP 401."""
        fake_user = _make_fake_user()
        fake_user.verify_password = MagicMock(return_value=False)

        with patch(
            "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_email_hash",
            new=AsyncMock(return_value=fake_user),
        ):
            response = await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "senha_errada"},
            )

        assert response.status_code == 401

    async def test_login_inactive_user_returns_401(self, auth_client):
        """Login com conta inativa retorna HTTP 401."""
        fake_user = _make_fake_user()
        fake_user.is_active = False

        with patch(
            "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_email_hash",
            new=AsyncMock(return_value=fake_user),
        ):
            response = await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "inactive@example.com", "password": "senha123"},
            )

        assert response.status_code == 401

    async def test_login_invalid_email_format_returns_422(self, auth_client):
        """Login com email em formato inválido retorna HTTP 422 (validação Pydantic)."""
        response = await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "nao_e_email", "password": "senha123"},
        )

        assert response.status_code == 422

    async def test_login_success_access_token_is_jwt(self, auth_client):
        """Login bem-sucedido retorna access_token no formato JWT (3 partes separadas por ponto)."""
        fake_user = _make_fake_user()
        fake_token = _make_fake_token()

        with (
            patch(
                "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_email_hash",
                new=AsyncMock(return_value=fake_user),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.create",
                new=AsyncMock(return_value=fake_token),
            ),
        ):
            response = await auth_client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "senha_correta"},
            )

        assert response.status_code == 200
        data = response.json()
        # JWT tem exatamente 3 partes separadas por ponto
        assert len(data["access_token"].split(".")) == 3


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    async def test_refresh_invalid_token_returns_401(self, auth_client):
        """Refresh com token inválido retorna HTTP 401."""
        with patch(
            "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
            new=AsyncMock(return_value=None),
        ):
            response = await auth_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid_token_value"},
            )

        assert response.status_code == 401

    async def test_refresh_missing_field_returns_422(self, auth_client):
        """Refresh sem campo refresh_token retorna HTTP 422."""
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422

    async def test_refresh_success_returns_200_with_new_tokens(self, auth_client):
        """Refresh com token válido retorna HTTP 200 com novo par de tokens."""
        fake_user = _make_fake_user()
        fake_refresh_db = _make_fake_token()
        fake_new_token = _make_fake_token()

        with (
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
                new=AsyncMock(return_value=fake_refresh_db),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.revoke",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "src.infrastructure.repositories.user_repository.SQLUserRepository.get_by_id",
                new=AsyncMock(return_value=fake_user),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.create",
                new=AsyncMock(return_value=fake_new_token),
            ),
        ):
            response = await auth_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid_refresh_token_value"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_revoked_token_returns_401(self, auth_client):
        """Refresh com token já revogado retorna HTTP 401 (valida R7)."""
        with patch(
            "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
            new=AsyncMock(return_value=None),  # Token não encontrado = revogado ou expirado
        ):
            response = await auth_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "revoked_token_value"},
            )

        assert response.status_code == 401

    async def test_refresh_empty_token_returns_422(self, auth_client):
        """Refresh com refresh_token vazio retorna HTTP 422 (validação Pydantic)."""
        response = await auth_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": ""},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------


class TestLogoutEndpoint:
    async def test_logout_valid_token_returns_204(self, auth_client):
        """Logout com token válido retorna HTTP 204 sem corpo."""
        with (
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
                new=AsyncMock(return_value=_make_fake_token()),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.revoke",
                new=AsyncMock(return_value=None),
            ),
        ):
            response = await auth_client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "any_valid_token"},
            )

        assert response.status_code == 204

    async def test_logout_invalid_token_still_returns_204(self, auth_client):
        """Logout com token inválido também retorna HTTP 204 (operação silenciosa)."""
        with patch(
            "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
            new=AsyncMock(return_value=None),
        ):
            response = await auth_client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "already_expired_token"},
            )

        assert response.status_code == 204

    async def test_logout_missing_token_returns_422(self, auth_client):
        """Logout sem refresh_token retorna HTTP 422."""
        response = await auth_client.post(
            "/api/v1/auth/logout",
            json={},
        )

        assert response.status_code == 422

    async def test_logout_response_has_no_body(self, auth_client):
        """Logout bem-sucedido retorna 204 sem corpo de resposta."""
        with (
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.get_valid_token",
                new=AsyncMock(return_value=_make_fake_token()),
            ),
            patch(
                "src.infrastructure.repositories.token_repository.SQLTokenRepository.revoke",
                new=AsyncMock(return_value=None),
            ),
        ):
            response = await auth_client.post(
                "/api/v1/auth/logout",
                json={"refresh_token": "valid_token"},
            )

        assert response.status_code == 204
        assert response.content == b""


# ---------------------------------------------------------------------------
# POST /api/v1/auth/admin/schedule-token-cleanup
# ---------------------------------------------------------------------------


class TestScheduleTokenCleanupEndpoint:
    async def test_schedule_token_cleanup_returns_201(self, auth_client, mock_session):
        """Agendamento de limpeza de tokens retorna HTTP 201."""
        response = await auth_client.post("/api/v1/auth/admin/schedule-token-cleanup")

        assert response.status_code == 201

    async def test_schedule_token_cleanup_returns_mensagem(self, auth_client, mock_session):
        """Agendamento de limpeza retorna JSON com chave 'mensagem'."""
        response = await auth_client.post("/api/v1/auth/admin/schedule-token-cleanup")

        assert response.status_code == 201
        data = response.json()
        assert "mensagem" in data

    async def test_schedule_token_cleanup_adds_task_to_session(self, auth_client, mock_session):
        """Agendamento de limpeza adiciona uma TaskQueue à sessão do banco."""
        response = await auth_client.post("/api/v1/auth/admin/schedule-token-cleanup")

        assert response.status_code == 201
        # session.add deve ter sido chamado com uma TaskQueue
        mock_session.add.assert_called_once()
