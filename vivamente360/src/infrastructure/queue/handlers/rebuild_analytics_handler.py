"""Handler para tarefas do tipo 'compute_scores' (rebuild analytics).

Payload esperado:
    {
        "survey_response_id": "<UUID da resposta>",
        "campaign_id": "<UUID da campanha>"
    }

Regra R3: O dashboard NUNCA calcula em tempo real.
Este handler é disparado quando uma SurveyResponse é submetida e popula
as tabelas do Modelo Estrela (FactScoreDimensao e dimensionais) de forma
assíncrona, sem bloquear o request/response cycle.
"""
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.base_handler import BaseTaskHandler

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset({"survey_response_id", "campaign_id"})


class RebuildAnalyticsHandler(BaseTaskHandler):
    """Reconstrói as tabelas analíticas do Modelo Estrela para uma survey_response.

    Disparado automaticamente após cada submissão de resposta, garante que
    o dashboard sempre leia dados pré-computados (zero cálculos em runtime).
    Implementação completa depende do Blueprint do Modelo Estrela.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Recalcula scores e popula o Modelo Estrela para a resposta indicada.

        Args:
            payload: Dicionário com survey_response_id e campaign_id.

        Raises:
            ValueError: Se o payload estiver incompleto ou com UUIDs inválidos.
            RuntimeError: Se os dados da resposta não forem encontrados.
        """
        self._validate_payload(payload)

        survey_response_id: UUID = self._parse_uuid(
            payload["survey_response_id"], "survey_response_id"
        )
        campaign_id: UUID = self._parse_uuid(payload["campaign_id"], "campaign_id")

        logger.info(
            "Reconstruindo analytics: survey_response_id=%s campaign_id=%s",
            survey_response_id,
            campaign_id,
        )

        # TODO (Blueprint Modelo Estrela): implementar o pipeline de cálculo:
        #
        # 1. Carregar SurveyResponse com respostas JSONB
        #    response = await survey_response_repo.get_by_id(survey_response_id)
        #
        # 2. Calcular scores por dimensão (ex: via ScoreService)
        #    scores = score_service.compute(response.respostas)
        #
        # 3. Persistir em FactScoreDimensao (modelo estrela)
        #    await analytics_repo.upsert_fact(survey_response_id, campaign_id, scores)
        #
        # 4. Atualizar métricas agregadas da campanha (DimCampanha)
        #    await analytics_repo.refresh_campaign_metrics(campaign_id)

        logger.info(
            "Analytics reconstruído com sucesso: survey_response_id=%s",
            survey_response_id,
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
                f"Payload inválido para compute_scores. Campos ausentes: {sorted(missing)}"
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
