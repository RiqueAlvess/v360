"""Service de notificações in-app — Módulo 08.

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.

Interface interna: NotificationService é chamado por outros services
(CampaignService, WhistleblowerService, etc.) para criar notificações in-app.
Não usa task queue — notificações são escritas diretamente no banco.
"""
import logging
import math
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.notification_tipo import NotificationTipo
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.models.notification import Notification
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.repositories.notification_repository import (
    NotificationRepository,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Cria e gerencia notificações in-app para usuários da plataforma.

    Responsabilidades:
    - notify(): cria notificação para um usuário específico.
    - notify_by_role(): notifica todos os usuários de um role na empresa.
    - list_notifications(): lista notificações visíveis com paginação.
    - count_unread(): retorna badge count de não lidas.
    - mark_read(): marca uma notificação como lida.
    - mark_all_read(): marca todas as notificações como lidas.
    - delete_notification(): soft delete de uma notificação.
    - clear_all_read(): soft delete em massa de notificações lidas.
    """

    def __init__(
        self,
        notification_repo: NotificationRepository,
        db: AsyncSession,
    ) -> None:
        self._repo = notification_repo
        self._db = db

    async def notify(
        self,
        company_id: UUID,
        user_id: UUID,
        tipo: NotificationTipo,
        titulo: str,
        mensagem: str,
        link: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Notification:
        """Cria notificação in-app para um usuário específico.

        Chamado por outros services ao ocorrer um evento do sistema.
        Escrita direta no banco — sem task queue.

        Args:
            company_id: UUID da empresa para isolamento multi-tenant.
            user_id: UUID do destinatário da notificação.
            tipo: Tipo do evento que gerou a notificação.
            titulo: Título curto da notificação.
            mensagem: Mensagem detalhada do evento.
            link: Rota frontend para navegar ao item (opcional).
            metadata: Dados extras estruturados (campaign_id, plan_id, etc.).

        Returns:
            A Notification criada.
        """
        notification = await self._repo.create(
            company_id=company_id,
            user_id=user_id,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            link=link,
            metadata=metadata or {},
        )

        logger.debug(
            "Notificação criada: user_id=%s tipo=%s id=%s",
            user_id,
            tipo.value,
            notification.id,
        )

        return notification

    async def notify_by_role(
        self,
        company_id: UUID,
        role: UserRole,
        tipo: NotificationTipo,
        titulo: str,
        mensagem: str,
        link: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """Notifica todos os usuários ativos de um role na empresa.

        Útil para eventos que afetam todos os admins/HRs da empresa.
        Cada usuário recebe uma notificação individual.

        Args:
            company_id: UUID da empresa.
            role: Role alvo (ADMIN, MANAGER ou RESPONDENT).
            tipo: Tipo do evento.
            titulo: Título da notificação.
            mensagem: Mensagem do evento.
            link: Rota frontend opcional.
            metadata: Dados extras opcionais.

        Returns:
            Número de notificações criadas.
        """
        # Busca IDs dos usuários ativos com o role na empresa
        result = await self._db.execute(
            select(UserModel.id).where(
                UserModel.company_id == company_id,
                UserModel.role == role,
                UserModel.ativo.is_(True),
            )
        )
        user_ids: list[UUID] = list(result.scalars().all())

        if not user_ids:
            logger.debug(
                "Nenhum usuário com role=%s na empresa %s para notificar.",
                role.value,
                company_id,
            )
            return 0

        count = 0
        for user_id in user_ids:
            await self._repo.create(
                company_id=company_id,
                user_id=user_id,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
                link=link,
                metadata=metadata or {},
            )
            count += 1

        logger.info(
            "Notificações em massa: company_id=%s role=%s tipo=%s count=%d",
            company_id,
            role.value,
            tipo.value,
            count,
        )

        return count

    async def list_notifications(
        self,
        user_id: UUID,
        lida: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Lista notificações visíveis do usuário com paginação e badge count.

        Args:
            user_id: UUID do usuário autenticado.
            lida: Filtro opcional — True=lidas, False=não lidas, None=todas.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).

        Returns:
            Dict com 'items', 'total_nao_lidas' (badge) e 'pagination'.
        """
        items, total, total_nao_lidas = await self._repo.list_by_user(
            user_id=user_id,
            lida=lida,
            page=page,
            page_size=page_size,
        )

        pages = math.ceil(total / page_size) if total > 0 else 0

        return {
            "items": items,
            "total_nao_lidas": total_nao_lidas,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }

    async def count_unread(self, user_id: UUID) -> int:
        """Retorna o badge count de notificações não lidas.

        Endpoint leve — usado para polling a cada 60s pelo frontend.

        Args:
            user_id: UUID do usuário autenticado.

        Returns:
            Número de notificações não lidas e não deletadas.
        """
        return await self._repo.count_unread(user_id)

    async def mark_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> Optional[Notification]:
        """Marca uma notificação como lida.

        Args:
            notification_id: UUID da notificação.
            user_id: UUID do usuário — validação de posse.

        Returns:
            A Notification atualizada, ou None se não encontrada.
        """
        return await self._repo.mark_read(
            notification_id=notification_id,
            user_id=user_id,
        )

    async def mark_all_read(self, user_id: UUID) -> int:
        """Marca todas as notificações não lidas como lidas em uma operação.

        Args:
            user_id: UUID do usuário autenticado.

        Returns:
            Número de notificações atualizadas.
        """
        return await self._repo.mark_all_read(user_id)

    async def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Soft delete de uma notificação (deletada=True + deletada_em=NOW()).

        O item desaparece da listagem mas permanece no banco para auditoria.

        Args:
            notification_id: UUID da notificação.
            user_id: UUID do usuário — validação de posse.

        Returns:
            True se deletada, False se não encontrada.
        """
        return await self._repo.soft_delete(
            notification_id=notification_id,
            user_id=user_id,
        )

    async def clear_all_read(self, user_id: UUID) -> int:
        """Soft delete em todas as notificações lidas do usuário.

        Args:
            user_id: UUID do usuário autenticado.

        Returns:
            Número de notificações deletadas.
        """
        return await self._repo.soft_delete_all_read(user_id)
