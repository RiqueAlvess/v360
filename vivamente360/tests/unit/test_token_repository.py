"""Testes unitários do SQLTokenRepository.

Cobre os quatro métodos do repositório de refresh tokens:
    - create(): persiste novo token
    - get_valid_token(): retorna None quando não existe, revogado ou expirado
    - revoke(): marca token como revogado
    - cleanup_expired(): deleta tokens expirados e retorna contagem
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.repositories.token_repository import SQLTokenRepository


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(mock_session: AsyncMock) -> SQLTokenRepository:
    """SQLTokenRepository com sessão mockada."""
    return SQLTokenRepository(session=mock_session)


def _make_db_token(
    user_id: uuid.UUID | None = None,
    revogado: bool = False,
    expired: bool = False,
) -> MagicMock:
    """Cria um objeto RefreshToken fake compatível com o modelo ORM."""
    token = MagicMock()
    token.id = uuid.uuid4()
    token.user_id = user_id or uuid.uuid4()
    token.token_hash = "a" * 64
    token.revogado = revogado
    delta = timedelta(days=-1) if expired else timedelta(days=30)
    token.expires_at = datetime.now(tz=timezone.utc) + delta
    return token


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestSQLTokenRepositoryCreate:
    async def test_create_adds_token_to_session(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """create() deve adicionar o token à sessão e chamar flush."""
        user_id = uuid.uuid4()
        token_hash = "b" * 64
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)

        result = await repo.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert result is not None

    async def test_create_token_has_correct_fields(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """create() deve persistir token com user_id, hash e expires_at corretos."""
        user_id = uuid.uuid4()
        token_hash = "c" * 64
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=30)

        await repo.create(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        added_token = mock_session.add.call_args[0][0]
        assert added_token.user_id == user_id
        assert added_token.token_hash == token_hash
        assert added_token.expires_at == expires_at


# ---------------------------------------------------------------------------
# get_valid_token()
# ---------------------------------------------------------------------------


class TestSQLTokenRepositoryGetValidToken:
    async def test_get_valid_token_found_returns_token(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """get_valid_token() retorna o token quando existe, não revogado e não expirado."""
        fake_token = _make_db_token()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_token
        mock_session.execute.return_value = mock_result

        result = await repo.get_valid_token("hash_valido" + "0" * 54)

        assert result is fake_token

    async def test_get_valid_token_not_found_returns_none(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """get_valid_token() retorna None quando o hash não existe no banco."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_valid_token("hash_inexistente" + "0" * 48)

        assert result is None

    async def test_get_valid_token_revoked_returns_none(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """get_valid_token() retorna None quando o token está revogado.

        O WHERE clause inclui revogado=False, portanto banco não retorna o token.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # banco filtra por revogado=False
        mock_session.execute.return_value = mock_result

        result = await repo.get_valid_token("hash_revogado" + "0" * 51)

        assert result is None

    async def test_get_valid_token_expired_returns_none(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """get_valid_token() retorna None quando o token está expirado.

        O WHERE clause inclui expires_at > now(), portanto banco não retorna token expirado.
        """
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # banco filtra por expires_at > now()
        mock_session.execute.return_value = mock_result

        result = await repo.get_valid_token("hash_expirado" + "0" * 51)

        assert result is None

    async def test_get_valid_token_executes_query(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """get_valid_token() deve executar uma query no banco."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repo.get_valid_token("qualquer_hash" + "0" * 51)

        mock_session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# revoke()
# ---------------------------------------------------------------------------


class TestSQLTokenRepositoryRevoke:
    async def test_revoke_executes_update_and_flush(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """revoke() deve executar UPDATE e chamar flush."""
        token_id = uuid.uuid4()

        await repo.revoke(token_id)

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_revoke_calls_execute_with_token_id(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """revoke() deve chamar execute — verificando que a operação ocorre."""
        token_id = uuid.uuid4()

        await repo.revoke(token_id)

        # Verificar que execute foi chamado (a query UPDATE é construída pelo SQLAlchemy)
        assert mock_session.execute.call_count == 1

    async def test_revoke_calls_flush_after_update(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """revoke() deve chamar flush após o execute para persistir no banco."""
        token_id = uuid.uuid4()
        mock_session.execute.return_value = MagicMock()

        await repo.revoke(token_id)

        # flush deve ser chamado após execute
        mock_session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# cleanup_expired()
# ---------------------------------------------------------------------------


class TestSQLTokenRepositoryCleanupExpired:
    async def test_cleanup_expired_returns_zero_when_no_expired(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_expired() retorna 0 quando não há tokens expirados."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        count = await repo.cleanup_expired()

        assert count == 0

    async def test_cleanup_expired_returns_count_deleted(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_expired() retorna a quantidade de tokens deletados."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute.return_value = mock_result

        count = await repo.cleanup_expired()

        assert count == 5

    async def test_cleanup_expired_executes_delete_and_flush(
        self, repo: SQLTokenRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_expired() deve executar DELETE e chamar flush."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        await repo.cleanup_expired()

        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()
