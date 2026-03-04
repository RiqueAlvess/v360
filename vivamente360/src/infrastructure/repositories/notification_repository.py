"""Repositório de notificações in-app — Módulo 08.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: list_by_user() retorna tupla (items, total) para paginação obrigatória.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.notification_tipo import NotificationTipo
from src.infrastructure.database.models.notification import Notification

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class NotificationRepository(ABC):
    """Interface abstrata do repositório de notificações."""

    @abstractmethod
    async def create(
        self,
        company_id: UUID,
        user_id: UUID,
        tipo: NotificationTipo,
        titulo: str,
        mensagem: str,
        link: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Cria e persiste uma nova notificação in-app."""
        ...

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        lida: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """Lista notificações visíveis do usuário com paginação.

        Retorna apenas notificações com deletada=False.

        Returns:
            Tupla (items, total_filtrado, total_nao_lidas) onde:
                - items: notificações da página
                - total_filtrado: total respeitando filtro de lida
                - total_nao_lidas: badge count (sempre sem filtro de lida)
        """
        ...

    @abstractmethod
    async def count_unread(self, user_id: UUID) -> int:
        """Conta notificações não lidas e não deletadas do usuário (badge)."""
        ...

    @abstractmethod
    async def get_by_id(self, notification_id: UUID) -> Optional[Notification]:
        """Busca notificação pelo UUID."""
        ...

    @abstractmethod
    async def mark_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Optional[Notification]:
        """Marca uma notificação como lida. Retorna None se não encontrada."""
        ...

    @abstractmethod
    async def mark_all_read(self, user_id: UUID) -> int:
        """Marca todas as notificações não lidas do usuário como lidas.

        Returns:
            Número de notificações atualizadas.
        """
        ...

    @abstractmethod
    async def soft_delete(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete de uma notificação (deletada=True, deletada_em=NOW()).

        Returns:
            True se encontrada e deletada, False se não encontrada.
        """
        ...

    @abstractmethod
    async def soft_delete_all_read(self, user_id: UUID) -> int:
        """Soft delete em todas as notificações lidas do usuário.

        Returns:
            Número de notificações deletadas.
        """
        ...


class SQLNotificationRepository(NotificationRepository):
    """Implementação SQLAlchemy 2.x do repositório de notificações."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        company_id: UUID,
        user_id: UUID,
        tipo: NotificationTipo,
        titulo: str,
        mensagem: str,
        link: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Notification:
        """Cria e persiste nova notificação com flush (sem commit)."""
        notification = Notification(
            id=uuid.uuid4(),
            company_id=company_id,
            user_id=user_id,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            link=link,
            metadata_=metadata or {},
        )
        self._session.add(notification)
        await self._session.flush()
        return notification

    async def list_by_user(
        self,
        user_id: UUID,
        lida: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Notification], int, int]:
        """Retorna notificações visíveis paginadas e o badge de não lidas."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        # Base: apenas não deletadas
        base_stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.deletada.is_(False),
        )

        if lida is not None:
            base_stmt = base_stmt.where(Notification.lida.is_(lida))

        # Total respeitando o filtro de lida
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Badge: sempre conta não lidas independente do filtro
        badge_stmt = select(func.count()).where(
            Notification.user_id == user_id,
            Notification.deletada.is_(False),
            Notification.lida.is_(False),
        )
        badge_result = await self._session.execute(badge_stmt)
        total_nao_lidas: int = badge_result.scalar_one()

        # Itens paginados, mais recentes primeiro
        items_stmt = (
            base_stmt
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items: list[Notification] = list(items_result.scalars().all())

        return items, total, total_nao_lidas

    async def count_unread(self, user_id: UUID) -> int:
        """Conta via índice parcial idx_notifications_user_unread."""
        result = await self._session.execute(
            select(func.count()).where(
                Notification.user_id == user_id,
                Notification.lida.is_(False),
                Notification.deletada.is_(False),
            )
        )
        return result.scalar_one()

    async def get_by_id(self, notification_id: UUID) -> Optional[Notification]:
        """Busca notificação pelo UUID, retorna None se não existir."""
        result = await self._session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def mark_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Optional[Notification]:
        """Marca notificação como lida. Ignorada se já lida ou deletada."""
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deletada.is_(False),
            )
            .values(lida=True, lida_em=now)
            .returning(Notification)
        )
        result = await self._session.execute(stmt)
        notification = result.scalar_one_or_none()
        if notification:
            await self._session.flush()
        return notification

    async def mark_all_read(self, user_id: UUID) -> int:
        """Atualiza em batch — uma única operação SQL para todas as não lidas."""
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.lida.is_(False),
                Notification.deletada.is_(False),
            )
            .values(lida=True, lida_em=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def soft_delete(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete: seta deletada=True + deletada_em sem hard delete."""
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deletada.is_(False),
            )
            .values(deletada=True, deletada_em=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0  # type: ignore[operator]

    async def soft_delete_all_read(self, user_id: UUID) -> int:
        """Soft delete em batch apenas nas notificações já lidas."""
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.lida.is_(True),
                Notification.deletada.is_(False),
            )
            .values(deletada=True, deletada_em=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]
