"""Testes unitários do AuthService.

Cobre os três fluxos principais:
    - login(): sucesso, credenciais inválidas, conta inativa
    - refresh(): sucesso, token inválido, rotação de token
    - logout(): sucesso, token já inválido (silencioso)
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.auth_service import AuthService
from src.shared.exceptions import UnauthorizedError


@pytest.fixture
def auth_service(mock_user_repo, mock_token_repo):
    return AuthService(
        user_repo=mock_user_repo,
        token_repo=mock_token_repo,
    )


def _make_fake_user(active: bool = True):
    """Cria um objeto User fake compatível com o domain entity."""
    user = MagicMock()
    user.id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    user.company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user.role = MagicMock()
    user.role.value = "admin"
    user.is_active = active
    user.verify_password = MagicMock(return_value=True)
    return user


def _make_fake_refresh_token(user_id: uuid.UUID):
    """Cria um RefreshToken fake para testes de refresh/logout."""
    token = MagicMock()
    token.id = uuid.uuid4()
    token.user_id = user_id
    token.revogado = False
    token.expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)
    return token


# ---------------------------------------------------------------------------
# login()
# ---------------------------------------------------------------------------


class TestAuthServiceLogin:
    async def test_login_success_returns_token_pair(self, auth_service, mock_user_repo, mock_token_repo):
        """Login com credenciais válidas retorna access_token e refresh_token."""
        fake_user = _make_fake_user()
        mock_user_repo.get_by_email_hash.return_value = fake_user
        mock_token_repo.create.return_value = MagicMock()

        result = await auth_service.login("user@example.com", "senha_correta")

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    async def test_login_user_not_found_raises_unauthorized(self, auth_service, mock_user_repo):
        """Login com email não cadastrado levanta UnauthorizedError."""
        mock_user_repo.get_by_email_hash.return_value = None

        with pytest.raises(UnauthorizedError) as exc_info:
            await auth_service.login("unknown@example.com", "qualquer_senha")

        assert "Credenciais" in exc_info.value.detail

    async def test_login_wrong_password_raises_unauthorized(self, auth_service, mock_user_repo):
        """Login com senha incorreta levanta UnauthorizedError."""
        fake_user = _make_fake_user()
        fake_user.verify_password.return_value = False
        mock_user_repo.get_by_email_hash.return_value = fake_user

        with pytest.raises(UnauthorizedError):
            await auth_service.login("user@example.com", "senha_errada")

    async def test_login_inactive_user_raises_unauthorized(self, auth_service, mock_user_repo):
        """Login com conta inativa levanta UnauthorizedError."""
        fake_user = _make_fake_user(active=False)
        mock_user_repo.get_by_email_hash.return_value = fake_user

        with pytest.raises(UnauthorizedError) as exc_info:
            await auth_service.login("user@example.com", "senha_correta")

        assert "desativada" in exc_info.value.detail.lower()

    async def test_login_normalizes_email(self, auth_service, mock_user_repo, mock_token_repo):
        """Email é normalizado (lowercase, strip) antes do lookup."""
        fake_user = _make_fake_user()
        mock_user_repo.get_by_email_hash.return_value = fake_user
        mock_token_repo.create.return_value = MagicMock()

        await auth_service.login("  USER@EXAMPLE.COM  ", "senha_correta")

        # Verificar que get_by_email_hash foi chamado com hash do email normalizado
        import hashlib
        expected_hash = hashlib.sha256("user@example.com".encode()).hexdigest()
        mock_user_repo.get_by_email_hash.assert_called_once_with(expected_hash)

    async def test_login_stores_token_hash_not_raw(self, auth_service, mock_user_repo, mock_token_repo):
        """Refresh token é armazenado como hash SHA-256, nunca em plaintext."""
        fake_user = _make_fake_user()
        mock_user_repo.get_by_email_hash.return_value = fake_user
        mock_token_repo.create.return_value = MagicMock()

        result = await auth_service.login("user@example.com", "senha_correta")

        # Verificar que create foi chamado com token_hash (64 hex chars = SHA-256)
        call_kwargs = mock_token_repo.create.call_args.kwargs
        stored_hash = call_kwargs["token_hash"]
        assert len(stored_hash) == 64  # SHA-256 hex digest
        assert stored_hash != result["refresh_token"]  # Nunca o valor raw


# ---------------------------------------------------------------------------
# refresh()
# ---------------------------------------------------------------------------


class TestAuthServiceRefresh:
    async def test_refresh_success_rotates_token(self, auth_service, mock_token_repo, mock_user_repo):
        """Refresh bem-sucedido revoga o token atual e emite novo par."""
        fake_user = _make_fake_user()
        fake_refresh = _make_fake_refresh_token(fake_user.id)

        mock_token_repo.get_valid_token.return_value = fake_refresh
        mock_user_repo.get_by_id.return_value = fake_user
        mock_token_repo.create.return_value = MagicMock()

        result = await auth_service.refresh("valid_refresh_token")

        # Token antigo deve ser revogado
        mock_token_repo.revoke.assert_called_once_with(fake_refresh.id)
        # Novo par deve ser retornado
        assert "access_token" in result
        assert "refresh_token" in result

    async def test_refresh_invalid_token_raises_unauthorized(self, auth_service, mock_token_repo):
        """Refresh com token inválido ou já revogado levanta UnauthorizedError."""
        mock_token_repo.get_valid_token.return_value = None

        with pytest.raises(UnauthorizedError) as exc_info:
            await auth_service.refresh("revoked_or_invalid_token")

        assert "inválido" in exc_info.value.detail.lower()

    async def test_refresh_inactive_user_raises_unauthorized(
        self, auth_service, mock_token_repo, mock_user_repo
    ):
        """Refresh com usuário inativo levanta UnauthorizedError."""
        fake_user = _make_fake_user(active=False)
        fake_refresh = _make_fake_refresh_token(fake_user.id)

        mock_token_repo.get_valid_token.return_value = fake_refresh
        mock_user_repo.get_by_id.return_value = fake_user

        with pytest.raises(UnauthorizedError):
            await auth_service.refresh("valid_but_user_inactive")


# ---------------------------------------------------------------------------
# logout()
# ---------------------------------------------------------------------------


class TestAuthServiceLogout:
    async def test_logout_revokes_valid_token(self, auth_service, mock_token_repo):
        """Logout revoga o refresh token."""
        fake_token = MagicMock()
        fake_token.id = uuid.uuid4()
        mock_token_repo.get_valid_token.return_value = fake_token

        await auth_service.logout("valid_refresh_token")

        mock_token_repo.revoke.assert_called_once_with(fake_token.id)

    async def test_logout_invalid_token_is_silent(self, auth_service, mock_token_repo):
        """Logout com token inválido não levanta erro — operação silenciosa."""
        mock_token_repo.get_valid_token.return_value = None

        # Não deve levantar exceção
        await auth_service.logout("invalid_or_expired_token")

        mock_token_repo.revoke.assert_not_called()
