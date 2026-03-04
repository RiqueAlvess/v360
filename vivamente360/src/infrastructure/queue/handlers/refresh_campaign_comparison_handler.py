"""Handler para tarefas do tipo 'refresh_campaign_comparison'.

Payload esperado:
    {
        "campaign_id": "<UUID da campanha que disparou o rebuild>"
    }

Responsabilidade única: executar REFRESH MATERIALIZED VIEW CONCURRENTLY
em campaign_comparison após cada rebuild_analytics concluído.

A view campaign_comparison agrega score_campanha por (campaign_id, dimensao)
e é usada pelo endpoint GET /dashboard/compare — zero cálculo em runtime (Regra R3).

Executado sempre após RebuildAnalyticsHandler via fila FIFO (agendado no mesmo
flush de sessão), garantindo que o comparativo reflita os dados mais recentes.
"""
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.base_handler import BaseTaskHandler

logger = logging.getLogger(__name__)


class RefreshCampaignComparisonHandler(BaseTaskHandler):
    """Atualiza a view materializada campaign_comparison após rebuild de analytics.

    Executa REFRESH MATERIALIZED VIEW CONCURRENTLY, que não bloqueia leituras
    simultâneas. Requer o índice único idx_campaign_comparison_pk criado na
    migration blueprint_09_dashboard_filters.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Executa o refresh da view materializada campaign_comparison.

        Usa CONCURRENTLY para não bloquear queries de leitura no dashboard
        durante a atualização. O índice único em (campaign_id, dimensao)
        é pré-requisito para o modo CONCURRENTLY.

        Args:
            payload: Dicionário com campaign_id (informativo, não utilizado
                     na query — o refresh é global sobre a view inteira).
        """
        campaign_id: str = payload.get("campaign_id", "desconhecido")
        logger.info(
            "Iniciando refresh campaign_comparison: campaign_id=%s", campaign_id
        )

        await self._db.execute(
            sa.text("REFRESH MATERIALIZED VIEW CONCURRENTLY campaign_comparison")
        )

        logger.info(
            "View campaign_comparison atualizada com sucesso: campaign_id=%s",
            campaign_id,
        )
