"""Handler para tarefas do tipo 'compute_scores' (rebuild analytics).

Payload esperado:
    {
        "campaign_id": "<UUID da campanha>"
    }

Regra R3: O dashboard NUNCA calcula em tempo real.
Este handler é disparado quando uma SurveyResponse é submetida e popula
as tabelas do Modelo Estrela (FactScoreDimensao e dimensionais) de forma
assíncrona, sem bloquear o request/response cycle.

Pipeline:
    1. Buscar TODAS as respostas da campanha (uma query, sem N+1).
    2. Determinar company_id a partir da campanha.
    3. Calcular scores por dimensão usando ScoreService.
    4. Obter ou criar dim_tempo para a data de hoje.
    5. Obter ou criar dim_estrutura para a empresa (nível companhia).
    6. Upsert em fact_score_dimensao (idempotente via ON CONFLICT DO UPDATE).
"""
import logging
from datetime import date, timezone
from datetime import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.score_service import ScoreService
from src.domain.enums.dimensao_hse import DimensaoHSE
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.repositories.analytics_repository import SQLAnalyticsRepository

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset({"campaign_id"})


class RebuildAnalyticsHandler(BaseTaskHandler):
    """Reconstrói as tabelas analíticas do Modelo Estrela para toda uma campanha.

    Disparado automaticamente após cada submissão de resposta, garante que
    o dashboard sempre leia dados pré-computados (zero cálculos em runtime).
    Idempotente: pode ser executado múltiplas vezes sem duplicar dados.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Recalcula scores e popula o Modelo Estrela para toda a campanha.

        Pipeline completo em uma única invocação:
        1. Validar e parsear payload.
        2. Carregar campanha para obter company_id.
        3. Carregar TODAS as respostas da campanha em uma query.
        4. Calcular scores por dimensão com ScoreService (em memória).
        5. Garantir dim_tempo e dim_estrutura existam.
        6. Upsert em fact_score_dimensao para cada dimensão com dados.

        Args:
            payload: Dicionário com campaign_id.

        Raises:
            ValueError: Se o payload estiver incompleto ou com UUIDs inválidos.
            RuntimeError: Se a campanha não for encontrada no banco.
        """
        self._validate_payload(payload)
        campaign_id: UUID = self._parse_uuid(payload["campaign_id"], "campaign_id")

        logger.info("Iniciando rebuild analytics: campaign_id=%s", campaign_id)

        # ---------------------------------------------------------------
        # 1. Carregar campanha para obter company_id
        # ---------------------------------------------------------------
        campaign_result = await self._db.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()

        if campaign is None:
            raise RuntimeError(
                f"Campanha não encontrada: campaign_id={campaign_id}"
            )

        company_id: UUID = campaign.company_id

        # ---------------------------------------------------------------
        # 2. Carregar TODAS as respostas da campanha em uma única query
        #    (elimina N+1 — Regra R3)
        # ---------------------------------------------------------------
        respostas_result = await self._db.execute(
            select(SurveyResponse.respostas).where(
                SurveyResponse.campaign_id == campaign_id
            )
        )
        respostas_lista: list[dict[str, Any]] = [
            row[0] for row in respostas_result.all()
        ]

        total_respostas_campanha = len(respostas_lista)
        logger.info(
            "Respostas carregadas: campaign_id=%s total=%d",
            campaign_id,
            total_respostas_campanha,
        )

        if total_respostas_campanha == 0:
            logger.warning(
                "Campanha sem respostas — nada a computar: campaign_id=%s", campaign_id
            )
            return

        # ---------------------------------------------------------------
        # 3. Calcular scores por dimensão em memória (sem I/O adicional)
        # ---------------------------------------------------------------
        score_service = ScoreService()
        analytics_repo = SQLAnalyticsRepository(self._db)

        # ---------------------------------------------------------------
        # 4. Garantir dim_tempo para a data de hoje
        # ---------------------------------------------------------------
        hoje: date = dt.now(tz=timezone.utc).date()
        dim_tempo = await analytics_repo.get_or_create_dim_tempo(hoje)

        # ---------------------------------------------------------------
        # 5. Garantir dim_estrutura de nível empresa (sem hierarquia)
        #    Futuras versões poderão segmentar por unidade/setor/cargo
        #    quando os dados estruturais estiverem disponíveis nas respostas
        # ---------------------------------------------------------------
        dim_estrutura = await analytics_repo.get_or_create_dim_estrutura(
            company_id=company_id,
        )

        # ---------------------------------------------------------------
        # 6. Upsert em fact_score_dimensao para cada dimensão HSE-IT
        # ---------------------------------------------------------------
        dimensoes_computadas = 0
        for dimensao in DimensaoHSE:
            resultado = score_service.calcular_score_dimensao(
                respostas_lista, dimensao
            )
            if resultado is None:
                logger.debug(
                    "Dimensão sem dados: campaign_id=%s dimensao=%s",
                    campaign_id,
                    dimensao.value,
                )
                continue

            score_medio, nivel_risco, total_dim = resultado

            await analytics_repo.upsert_fact_score(
                campaign_id=campaign_id,
                dim_tempo_id=dim_tempo.id,
                dim_estrutura_id=dim_estrutura.id,
                dimensao=dimensao,
                score_medio=score_medio,
                nivel_risco=nivel_risco,
                total_respostas=total_dim,
            )
            dimensoes_computadas += 1
            logger.debug(
                "Dimensão processada: campaign_id=%s dimensao=%s score=%.2f nivel=%s",
                campaign_id,
                dimensao.value,
                float(score_medio),
                nivel_risco.value,
            )

        logger.info(
            "Analytics reconstruído com sucesso: campaign_id=%s "
            "dimensoes=%d total_respostas=%d",
            campaign_id,
            dimensoes_computadas,
            total_respostas_campanha,
        )

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Verifica que todos os campos obrigatórios estão presentes.

        Args:
            payload: Payload recebido da tarefa.

        Raises:
            ValueError: Se algum campo obrigatório estiver ausente.
        """
        missing = _REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Payload inválido para compute_scores. "
                f"Campos ausentes: {sorted(missing)}"
            )

    def _parse_uuid(self, value: str, field_name: str) -> UUID:
        """Converte uma string em UUID com mensagem de erro clara.

        Args:
            value: String a converter.
            field_name: Nome do campo para mensagem de erro.

        Returns:
            UUID convertido.

        Raises:
            ValueError: Se o valor não for um UUID válido.
        """
        try:
            return UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Campo '{field_name}' não é um UUID válido: {value!r}"
            ) from exc
