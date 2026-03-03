from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User as UserEntity
from src.infrastructure.database.models.user import User as UserModel


class UserRepository(ABC):
    """Interface abstrata do repositório de usuários."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[UserEntity]:
        """Busca usuário pelo seu UUID primário."""
        ...

    @abstractmethod
    async def get_by_email_hash(self, email_hash: str) -> Optional[UserEntity]:
        """Busca usuário pelo SHA-256 do email — sem expor email em texto puro."""
        ...


class SQLUserRepository(UserRepository):
    """Implementação SQLAlchemy do repositório de usuários."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: UserModel) -> UserEntity:
        """Converte modelo ORM para entidade de domínio."""
        return UserEntity(
            id=model.id,
            company_id=model.company_id,
            email_hash=model.email_hash,
            email_criptografado=model.email_criptografado,
            hashed_password=model.hashed_password,
            role=model.role,
            ativo=model.ativo,
            nome=model.nome,
        )

    async def get_by_id(self, user_id: UUID) -> Optional[UserEntity]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email_hash(self, email_hash: str) -> Optional[UserEntity]:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email_hash == email_hash)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None
