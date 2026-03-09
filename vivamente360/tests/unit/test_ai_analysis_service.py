"""Testes unitários do AIAnalysisService — Blueprint 07.

Cobre:
    - request_analysis(): sucesso, tipo inválido, rate limit excedido
    - get_analysis(): sucesso, não encontrado, isolamento por empresa
    - list_analyses(): paginação correta, filtros opcionais
    - get_summary(): agrega análises concluídas corretamente
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.ai_analysis_service import AIAnalysisService
from src.shared.exceptions import NotFoundError, RateLimitError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ANALYSIS_ID = uuid.uuid4()


def _make_fake_analysis(
    analysis_id: uuid.UUID = None,
    company_id: uuid.UUID = COMPANY_ID,
    status: str = "pending",
    tipo: str = "sentimento",
    setor_id: uuid.UUID = None,
    resultado: dict = None,
    tokens_input: int = None,
    tokens_output: int = None,
    model_usado: str = None,
):
    analysis = MagicMock()
    analysis.id = analysis_id or uuid.uuid4()
    analysis.company_id = company_id
    analysis.campaign_id = CAMPAIGN_ID
    analysis.status = status
    analysis.tipo = tipo
    analysis.setor_id = setor_id
    analysis.dimensao = None
    analysis.resultado = resultado
    analysis.tokens_input = tokens_input
    analysis.tokens_output = tokens_output
    analysis.model_usado = model_usado
    analysis.erro = None
    analysis.prompt_versao = None
    analysis.created_at = datetime.now(tz=timezone.utc)
    analysis.updated_at = datetime.now(tz=timezone.utc)
    return analysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_analysis_repo():
    from src.infrastructure.repositories.ai_analysis_repository import AiAnalysisRepository

    repo = AsyncMock(spec=AiAnalysisRepository)
    return repo


@pytest.fixture
def mock_task_service():
    from src.infrastructure.queue.task_service import TaskService

    service = AsyncMock(spec=TaskService)
    service.enqueue = AsyncMock()
    return service


@pytest.fixture
def ai_service(mock_analysis_repo, mock_task_service):
    return AIAnalysisService(
        analysis_repo=mock_analysis_repo,
        task_service=mock_task_service,
    )


# ---------------------------------------------------------------------------
# request_analysis()
# ---------------------------------------------------------------------------


class TestAiAnalysisServiceRequestAnalysis:
    async def test_request_analysis_success_returns_pending(
        self, ai_service, mock_analysis_repo, mock_task_service
    ):
        """request_analysis com tipo válido cria registro pending e enfileira tarefa."""
        fake_analysis = _make_fake_analysis(status="pending")
        mock_analysis_repo.count_by_company_last_hour.return_value = 0
        mock_analysis_repo.create.return_value = fake_analysis

        result = await ai_service.request_analysis(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            tipo="sentimento",
            requested_by=USER_ID,
        )

        assert result["status"] == "pending"
        assert "analysis_id" in result
        mock_analysis_repo.create.assert_called_once()
        mock_task_service.enqueue.assert_called_once()

    async def test_request_analysis_invalid_tipo_raises_validation_error(
        self, ai_service, mock_analysis_repo
    ):
        """Tipo de análise inválido levanta ValidationError."""
        mock_analysis_repo.count_by_company_last_hour.return_value = 0

        with pytest.raises(ValidationError) as exc_info:
            await ai_service.request_analysis(
                company_id=COMPANY_ID,
                campaign_id=CAMPAIGN_ID,
                tipo="tipo_invalido",
                requested_by=USER_ID,
            )

        assert "tipo_invalido" in exc_info.value.detail.lower() or "tipo" in exc_info.value.detail.lower()

    async def test_request_analysis_rate_limit_exceeded_raises_rate_limit_error(
        self, ai_service, mock_analysis_repo
    ):
        """Rate limit excedido levanta RateLimitError."""
        from src.shared.config import settings

        mock_analysis_repo.count_by_company_last_hour.return_value = settings.OPENROUTER_RATE_LIMIT_PER_HOUR

        with pytest.raises(RateLimitError):
            await ai_service.request_analysis(
                company_id=COMPANY_ID,
                campaign_id=CAMPAIGN_ID,
                tipo="sentimento",
                requested_by=USER_ID,
            )

        mock_analysis_repo.create.assert_not_called()

    async def test_request_analysis_enqueues_correct_task_type(
        self, ai_service, mock_analysis_repo, mock_task_service
    ):
        """A tarefa enfileirada deve ser do tipo RUN_AI_ANALYSIS."""
        from src.domain.enums.task_queue_type import TaskQueueType

        fake_analysis = _make_fake_analysis()
        mock_analysis_repo.count_by_company_last_hour.return_value = 0
        mock_analysis_repo.create.return_value = fake_analysis

        await ai_service.request_analysis(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            tipo="diagnostico",
            requested_by=USER_ID,
        )

        call_kwargs = mock_task_service.enqueue.call_args
        assert call_kwargs.kwargs["tipo"] == TaskQueueType.RUN_AI_ANALYSIS

    async def test_request_analysis_with_setor_and_dimensao(
        self, ai_service, mock_analysis_repo, mock_task_service
    ):
        """request_analysis com setor_id e dimensao repassa corretamente para o repo."""
        setor_id = uuid.uuid4()
        fake_analysis = _make_fake_analysis(setor_id=setor_id)
        mock_analysis_repo.count_by_company_last_hour.return_value = 0
        mock_analysis_repo.create.return_value = fake_analysis

        result = await ai_service.request_analysis(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            tipo="recomendacoes",
            requested_by=USER_ID,
            setor_id=setor_id,
            dimensao="demandas",
        )

        assert result["status"] == "pending"
        create_kwargs = mock_analysis_repo.create.call_args.kwargs
        assert create_kwargs["setor_id"] == setor_id
        assert create_kwargs["dimensao"] == "demandas"


# ---------------------------------------------------------------------------
# get_analysis()
# ---------------------------------------------------------------------------


class TestAiAnalysisServiceGetAnalysis:
    async def test_get_analysis_success(self, ai_service, mock_analysis_repo):
        """Busca por análise existente da empresa retorna o objeto."""
        analysis_id = uuid.uuid4()
        fake_analysis = _make_fake_analysis(analysis_id=analysis_id, status="completed")
        mock_analysis_repo.get_by_id.return_value = fake_analysis

        result = await ai_service.get_analysis(analysis_id, COMPANY_ID)

        assert result.id == analysis_id

    async def test_get_analysis_not_found_raises_not_found(
        self, ai_service, mock_analysis_repo
    ):
        """Análise inexistente levanta NotFoundError."""
        mock_analysis_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await ai_service.get_analysis(uuid.uuid4(), COMPANY_ID)

    async def test_get_analysis_different_company_raises_not_found(
        self, ai_service, mock_analysis_repo
    ):
        """Análise de outra empresa levanta NotFoundError (isolamento multi-tenant)."""
        other_company = uuid.UUID("99999999-9999-9999-9999-999999999999")
        fake_analysis = _make_fake_analysis(company_id=other_company)
        mock_analysis_repo.get_by_id.return_value = fake_analysis

        with pytest.raises(NotFoundError):
            await ai_service.get_analysis(fake_analysis.id, COMPANY_ID)


# ---------------------------------------------------------------------------
# list_analyses()
# ---------------------------------------------------------------------------


class TestAiAnalysisServiceListAnalyses:
    async def test_list_analyses_returns_paginated_result(
        self, ai_service, mock_analysis_repo
    ):
        """Listagem retorna items com metadados de paginação."""
        fake_items = [_make_fake_analysis() for _ in range(3)]
        mock_analysis_repo.get_by_campaign.return_value = (fake_items, 3)

        result = await ai_service.list_analyses(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            page=1,
            page_size=20,
        )

        assert "items" in result
        assert "pagination" in result
        assert result["pagination"]["total"] == 3
        assert len(result["items"]) == 3

    async def test_list_analyses_empty_returns_empty_list(
        self, ai_service, mock_analysis_repo
    ):
        """Listagem sem análises retorna lista vazia com pagination."""
        mock_analysis_repo.get_by_campaign.return_value = ([], 0)

        result = await ai_service.list_analyses(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
        )

        assert result["items"] == []
        assert result["pagination"]["total"] == 0
        assert result["pagination"]["pages"] == 1

    async def test_list_analyses_with_tipo_filter(self, ai_service, mock_analysis_repo):
        """Filtro por tipo é repassado ao repositório."""
        mock_analysis_repo.get_by_campaign.return_value = ([], 0)

        await ai_service.list_analyses(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            tipo="sentimento",
        )

        call_kwargs = mock_analysis_repo.get_by_campaign.call_args.kwargs
        assert call_kwargs.get("tipo") == "sentimento"

    async def test_list_analyses_pagination_meta_calculated_correctly(
        self, ai_service, mock_analysis_repo
    ):
        """Total de páginas calculado corretamente."""
        fake_items = [_make_fake_analysis() for _ in range(5)]
        mock_analysis_repo.get_by_campaign.return_value = (fake_items, 45)

        result = await ai_service.list_analyses(
            company_id=COMPANY_ID,
            campaign_id=CAMPAIGN_ID,
            page=1,
            page_size=20,
        )

        # ceil(45/20) = 3
        assert result["pagination"]["pages"] == 3


# ---------------------------------------------------------------------------
# get_summary()
# ---------------------------------------------------------------------------


class TestAiAnalysisServiceGetSummary:
    async def test_get_summary_returns_correct_totals(
        self, ai_service, mock_analysis_repo
    ):
        """get_summary retorna totais por status corretamente."""
        all_items = [
            _make_fake_analysis(status="completed", tokens_input=100, tokens_output=50),
            _make_fake_analysis(status="completed", tokens_input=200, tokens_output=80),
            _make_fake_analysis(status="pending"),
            _make_fake_analysis(status="failed"),
        ]
        mock_analysis_repo.get_by_campaign.return_value = (all_items, 4)
        mock_analysis_repo.get_completed_by_campaign.return_value = all_items[:2]

        result = await ai_service.get_summary(CAMPAIGN_ID, COMPANY_ID)

        assert result["total_analyses"] == 4
        assert result["total_completed"] == 2
        assert result["total_pending"] == 1
        assert result["total_failed"] == 1
        assert result["tokens_input_total"] == 300
        assert result["tokens_output_total"] == 130

    async def test_get_summary_groups_by_setor(self, ai_service, mock_analysis_repo):
        """get_summary agrupa análises por setor corretamente."""
        setor_id = uuid.uuid4()
        completed = [
            _make_fake_analysis(status="completed", setor_id=setor_id, tipo="sentimento"),
            _make_fake_analysis(status="completed", setor_id=setor_id, tipo="diagnostico"),
        ]
        mock_analysis_repo.get_by_campaign.return_value = (completed, 2)
        mock_analysis_repo.get_completed_by_campaign.return_value = completed

        result = await ai_service.get_summary(CAMPAIGN_ID, COMPANY_ID)

        assert len(result["por_setor"]) == 1
        sector_summary = result["por_setor"][0]
        assert sector_summary["total_analyses"] == 2
        assert len(sector_summary["tipos_concluidos"]) == 2

    async def test_get_summary_extracts_recomendacoes(
        self, ai_service, mock_analysis_repo
    ):
        """get_summary extrai recomendações de análises de tipo 'diagnostico'."""
        resultado = {
            "recomendacoes": [
                {"titulo": "Ação urgente", "prioridade": "alta", "prazo": "imediato"},
                {"titulo": "Treinamento", "prioridade": "media", "prazo": "30d"},
            ]
        }
        completed = [
            _make_fake_analysis(
                status="completed",
                tipo="diagnostico",
                resultado=resultado,
            )
        ]
        mock_analysis_repo.get_by_campaign.return_value = (completed, 1)
        mock_analysis_repo.get_completed_by_campaign.return_value = completed

        result = await ai_service.get_summary(CAMPAIGN_ID, COMPANY_ID)

        assert len(result["recomendacoes_priorizadas"]) == 2
        # Deve estar ordenado: alta > media
        assert result["recomendacoes_priorizadas"][0]["prioridade"] == "alta"

    async def test_get_summary_ignores_non_diagnostico_for_recomendacoes(
        self, ai_service, mock_analysis_repo
    ):
        """Análises de tipo 'sentimento' não geram recomendações."""
        resultado = {"recomendacoes": [{"titulo": "Rec", "prioridade": "alta", "prazo": "imediato"}]}
        completed = [
            _make_fake_analysis(
                status="completed",
                tipo="sentimento",  # NÃO é 'diagnostico'
                resultado=resultado,
            )
        ]
        mock_analysis_repo.get_by_campaign.return_value = (completed, 1)
        mock_analysis_repo.get_completed_by_campaign.return_value = completed

        result = await ai_service.get_summary(CAMPAIGN_ID, COMPANY_ID)

        assert len(result["recomendacoes_priorizadas"]) == 0

    async def test_get_summary_empty_campaign_returns_zeros(
        self, ai_service, mock_analysis_repo
    ):
        """Campanha sem análises retorna zeros e listas vazias."""
        mock_analysis_repo.get_by_campaign.return_value = ([], 0)
        mock_analysis_repo.get_completed_by_campaign.return_value = []

        result = await ai_service.get_summary(CAMPAIGN_ID, COMPANY_ID)

        assert result["total_analyses"] == 0
        assert result["total_completed"] == 0
        assert result["por_setor"] == []
        assert result["recomendacoes_priorizadas"] == []
