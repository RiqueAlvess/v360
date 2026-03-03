from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.refresh_token import RefreshToken


class TokenRepository(ABC):
    """Interface abstrata do repositório de refresh tokens."""

    @abstractmethod
    async def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        """Persiste um novo refresh token no banco."""
        ...

    @abstractmethod
    async def get_valid_token(self, token_hash: str) -> Optional[RefreshToken]:
        """Busca token válido (não revogado e não expirado) pelo hash SHA-256."""
        ...

    @abstractmethod
    async def revoke(self, token_id: UUID) -> None:
        """Marca o token como revogado — usado na rotação e no logout."""
        ...

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove tokens expirados do banco. Retorna a quantidade deletada."""
        ...


class SQLTokenRepository(TokenRepository):
    """Implementação SQLAlchemy do repositório de refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_valid_token(self, token_hash: str) -> Optional[RefreshToken]:
        now = datetime.now(tz=timezone.utc)
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revogado == False,  # noqa: E712
                RefreshToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_id: UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .values(revogado=True)
        )
        await self._session.flush()

    async def cleanup_expired(self) -> int:
        """Deleta refresh tokens cujo expires_at já passou. Retorna total removido."""
        now = datetime.now(tz=timezone.utc)
        result = await self._session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        await self._session.flush()
        return result.rowcount
