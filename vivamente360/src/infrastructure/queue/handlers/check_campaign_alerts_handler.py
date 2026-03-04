"""Handler para tarefas do tipo 'check_campaign_alerts'.

Job recorrente diário que detecta e notifica:
    1. Campanhas ativas com taxa de resposta < 30% → notifica HR da empresa.
    2. Planos de ação vencendo nos próximos 7 dias → notifica responsável.
    3. Campanhas que atingiram data_fim e ainda estão ACTIVE → fecha e notifica HR.

Payload esperado:
    {} (sem payload — o handler varre o banco inteiro)

Regra R2: Handler não contém lógica de negócio — apenas orquestra infraestrutura.
Regra R1: Type hints completos em todos os métodos.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.campaign_status import CampaignStatus
from src.domain.enums.notification_tipo import NotificationTipo
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.models.action_plan import ActionPlan
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.invitation import Invitation
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.repositories.notification_repository import (
    SQLNotificationRepository,
)
from src.application.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Threshold de taxa de resposta para alerta
_RESPONSE_RATE_THRESHOLD: float = 0.30

# Janela de alerta para planos vencendo (em dias)
_PLAN_EXPIRY_ALERT_DAYS: int = 7


class CheckCampaignAlertsHandler(BaseTaskHandler):
    """Processa o job diário de alertas de campanhas e planos de ação.

    Executado uma vez por dia via task_queue agendada.
    Varre todas as campanhas e planos ativos sem filtro de empresa
    — o worker tem acesso privilegiado (sem RLS de tenant).

    Fluxo:
        1. Fechar campanhas vencidas (data_fim < hoje, status=ACTIVE).
        2. Verificar taxa de resposta de campanhas ativas.
        3. Alertar sobre planos de ação vencendo em 7 dias.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._notification_service = NotificationService(
            notification_repo=SQLNotificationRepository(db),
            db=db,
        )

    async def execute(self, payload: dict[str, Any]) -> None:
        """Executa as três verificações de alerta.

        Args:
            payload: Ignorado para este handler (job sem parâmetros).
        """
        today = date.today()

        logger.info("check_campaign_alerts iniciado: data=%s", today)

        closed = await self._close_expired_campaigns(today)
        logger.info("Campanhas encerradas: %d", closed)

        low_rate_alerts = await self._check_low_response_rate(today)
        logger.info("Alertas de taxa de resposta baixa: %d", low_rate_alerts)

        plan_alerts = await self._check_expiring_plans(today)
        logger.info("Alertas de planos vencendo: %d", plan_alerts)

        logger.info(
            "check_campaign_alerts concluído: fechadas=%d low_rate=%d plans=%d",
            closed,
            low_rate_alerts,
            plan_alerts,
        )

    # -----------------------------------------------------------------------
    # 1. Fechar campanhas que atingiram data_fim
    # -----------------------------------------------------------------------

    async def _close_expired_campaigns(self, today: date) -> int:
        """Fecha campanhas ACTIVE cuja data_fim foi ultrapassada e notifica HR.

        Returns:
            Número de campanhas fechadas.
        """
        stmt = select(Campaign).where(
            Campaign.status == CampaignStatus.ACTIVE,
            Campaign.data_fim < today,
        )
        result = await self._db.execute(stmt)
        expired_campaigns: list[Campaign] = list(result.scalars().all())

        count = 0
        for campaign in expired_campaigns:
            # Atualiza status para COMPLETED
            await self._db.execute(
                update(Campaign)
                .where(Campaign.id == campaign.id)
                .values(status=CampaignStatus.COMPLETED)
            )

            # Notifica usuários com role MANAGER (HR) da empresa
            await self._notification_service.notify_by_role(
                company_id=campaign.company_id,
                role=UserRole.MANAGER,
                tipo=NotificationTipo.CAMPANHA_ENCERRADA,
                titulo="Campanha encerrada",
                mensagem=(
                    f"A campanha '{campaign.nome}' foi encerrada. "
                    "Acesse o dashboard para ver os resultados."
                ),
                link=f"/campaigns/{campaign.id}/dashboard",
                metadata={"campaign_id": str(campaign.id)},
            )

            # Notifica também admins
            await self._notification_service.notify_by_role(
                company_id=campaign.company_id,
                role=UserRole.ADMIN,
                tipo=NotificationTipo.CAMPANHA_ENCERRADA,
                titulo="Campanha encerrada",
                mensagem=(
                    f"A campanha '{campaign.nome}' foi encerrada. "
                    "Acesse o dashboard para ver os resultados."
                ),
                link=f"/campaigns/{campaign.id}/dashboard",
                metadata={"campaign_id": str(campaign.id)},
            )

            count += 1
            logger.info(
                "Campanha encerrada automaticamente: id=%s nome=%s empresa=%s",
                campaign.id,
                campaign.nome,
                campaign.company_id,
            )

        if count > 0:
            await self._db.flush()

        return count

    # -----------------------------------------------------------------------
    # 2. Verificar taxa de resposta < 30%
    # -----------------------------------------------------------------------

    async def _check_low_response_rate(self, today: date) -> int:
        """Identifica campanhas ativas com taxa de resposta abaixo do threshold.

        Calcula: total_respondidos / total_convidados por campanha.
        Notifica HR quando taxa < 30% (RESPONSE_RATE_THRESHOLD).

        Returns:
            Número de alertas enviados.
        """
        # Campanhas ativas que ainda não terminaram
        active_campaigns_stmt = select(Campaign).where(
            Campaign.status == CampaignStatus.ACTIVE,
            Campaign.data_fim >= today,
        )
        result = await self._db.execute(active_campaigns_stmt)
        active_campaigns: list[Campaign] = list(result.scalars().all())

        count = 0
        for campaign in active_campaigns:
            # Total de convidados
            total_stmt = select(func.count(Invitation.id)).where(
                Invitation.campaign_id == campaign.id
            )
            total_result = await self._db.execute(total_stmt)
            total_convidados: int = total_result.scalar_one()

            if total_convidados == 0:
                continue

            # Total que responderam
            respondidos_stmt = select(func.count(Invitation.id)).where(
                Invitation.campaign_id == campaign.id,
                Invitation.respondido.is_(True),
            )
            respondidos_result = await self._db.execute(respondidos_stmt)
            total_respondidos: int = respondidos_result.scalar_one()

            taxa = total_respondidos / total_convidados

            if taxa < _RESPONSE_RATE_THRESHOLD:
                pct = int(taxa * 100)

                await self._notification_service.notify_by_role(
                    company_id=campaign.company_id,
                    role=UserRole.MANAGER,
                    tipo=NotificationTipo.TAXA_RESPOSTA_BAIXA,
                    titulo="Taxa de resposta baixa",
                    mensagem=(
                        f"Campanha '{campaign.nome}': apenas {pct}% dos colaboradores "
                        "responderam. Considere reenviar os convites."
                    ),
                    link=f"/campaigns/{campaign.id}",
                    metadata={
                        "campaign_id": str(campaign.id),
                        "taxa_resposta": taxa,
                        "total_convidados": total_convidados,
                        "total_respondidos": total_respondidos,
                    },
                )

                count += 1
                logger.info(
                    "Alerta de taxa baixa: campaign_id=%s taxa=%.1f%% empresa=%s",
                    campaign.id,
                    taxa * 100,
                    campaign.company_id,
                )

        return count

    # -----------------------------------------------------------------------
    # 3. Alertar planos de ação vencendo em 7 dias
    # -----------------------------------------------------------------------

    async def _check_expiring_plans(self, today: date) -> int:
        """Notifica responsável de planos de ação que vencem nos próximos 7 dias.

        Busca planos PENDENTE ou EM_ANDAMENTO com prazo entre amanhã e +7 dias.

        Returns:
            Número de alertas enviados.
        """
        alert_horizon = today + timedelta(days=_PLAN_EXPIRY_ALERT_DAYS)

        stmt = select(ActionPlan).where(
            ActionPlan.status.in_(
                [ActionPlanStatus.PENDENTE, ActionPlanStatus.EM_ANDAMENTO]
            ),
            ActionPlan.prazo > today,
            ActionPlan.prazo <= alert_horizon,
        )
        result = await self._db.execute(stmt)
        expiring_plans: list[ActionPlan] = list(result.scalars().all())

        count = 0
        for plan in expiring_plans:
            # Calcula dias restantes
            dias_restantes = (plan.prazo - today).days

            # Notifica o responsável pelo plano se houver
            if plan.responsavel_id is not None:
                await self._notification_service.notify(
                    company_id=plan.company_id,
                    user_id=plan.responsavel_id,
                    tipo=NotificationTipo.PLANO_VENCENDO,
                    titulo="Plano de ação vencendo em breve",
                    mensagem=(
                        f"O plano '{plan.titulo}' vence em {dias_restantes} dia(s). "
                        "Atualize o status."
                    ),
                    link=f"/action-plans/{plan.campaign_id}/{plan.id}",
                    metadata={
                        "plan_id": str(plan.id),
                        "campaign_id": str(plan.campaign_id),
                        "prazo": str(plan.prazo),
                        "dias_restantes": dias_restantes,
                    },
                )
                count += 1
            else:
                # Sem responsável específico → notifica criador do plano
                await self._notification_service.notify(
                    company_id=plan.company_id,
                    user_id=plan.created_by,
                    tipo=NotificationTipo.PLANO_VENCENDO,
                    titulo="Plano de ação vencendo em breve",
                    mensagem=(
                        f"O plano '{plan.titulo}' vence em {dias_restantes} dia(s). "
                        "Atualize o status."
                    ),
                    link=f"/action-plans/{plan.campaign_id}/{plan.id}",
                    metadata={
                        "plan_id": str(plan.id),
                        "campaign_id": str(plan.campaign_id),
                        "prazo": str(plan.prazo),
                        "dias_restantes": dias_restantes,
                    },
                )
                count += 1

            logger.debug(
                "Alerta de prazo: plan_id=%s prazo=%s dias=%d empresa=%s",
                plan.id,
                plan.prazo,
                dias_restantes,
                plan.company_id,
            )

        return count
