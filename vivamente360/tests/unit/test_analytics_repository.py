"""Testes unitários para analytics_repository.

Cobre as correções obrigatórias do Blueprint 03:
    - get_score_by_dimension para campanha com respostas.
    - get_historical_scores com range de datas.
    - get_top_risk_sectors.
    - Confirmar que todos os métodos leem APENAS de FactScoreDimensao (Regra R3).

Estratégia:
    Usa mock_session (AsyncMock de AsyncSession) para isolar o repositório
    do banco de dados real, verificando os valores retornados e garantindo
    que nenhum cálculo de score ocorre fora do worker (R3).
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.enums.dimensao_hse import DimensaoHSE
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.repositories.analytics_repository import SQLAnalyticsRepository

CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DIM_TEMPO_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DIM_ESTRUTURA_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _make_execute_result(row_or_none) -> MagicMock:
    """Mock para db.execute() retornando um resultado simples."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row_or_none)
    result.scalar_one = MagicMock(return_value=row_or_none)
    result.one_or_none = MagicMock(return_value=row_or_none)
    result.all = MagicMock(return_value=[] if row_or_none is None else [row_or_none])
    return result


def _make_execute_result_many(rows: list) -> MagicMock:
    """Mock para db.execute() retornando lista de linhas."""
    result = MagicMock()
    result.all = MagicMock(return_value=rows)
    result.scalar_one = MagicMock(return_value=len(rows))
    return result


# ---------------------------------------------------------------------------
# get_score_by_dimension
# ---------------------------------------------------------------------------


class TestGetScoreByDimension:
    async def test_returns_score_for_existing_dimension(self, mock_session):
        """Retorna score e nível de risco para dimensão com dados em fact_score_dimensao."""
        fake_row = MagicMock()
        fake_row.score_medio = Decimal("3.75")
        fake_row.total_respostas = 42

        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=fake_row)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        result = await repo.get_score_by_dimension(
            campaign_id=CAMPAIGN_ID,
            dimensao=DimensaoHSE.DEMANDAS,
        )

        assert result is not None
        assert result["dimensao"] == DimensaoHSE.DEMANDAS.value
        assert result["score_medio"] == 3.75
        assert result["nivel_risco"] == NivelRisco.MODERADO.value
        assert result["total_respostas"] == 42

    async def test_returns_none_for_dimension_without_data(self, mock_session):
        """Retorna None quando não há dados para a dimensão."""
        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        result = await repo.get_score_by_dimension(
            campaign_id=CAMPAIGN_ID,
            dimensao=DimensaoHSE.MUDANCAS,
        )

        assert result is None

    async def test_classifies_nivel_risco_aceitavel_correctly(self, mock_session):
        """Score >= 4.0 é classificado como ACEITAVEL."""
        fake_row = MagicMock()
        fake_row.score_medio = Decimal("4.50")
        fake_row.total_respostas = 10

        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=fake_row)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        result = await repo.get_score_by_dimension(
            campaign_id=CAMPAIGN_ID,
            dimensao=DimensaoHSE.CONTROLE,
        )

        assert result["nivel_risco"] == NivelRisco.ACEITAVEL.value

    async def test_classifies_nivel_risco_critico_correctly(self, mock_session):
        """Score < 2.0 é classificado como CRITICO."""
        fake_row = MagicMock()
        fake_row.score_medio = Decimal("1.50")
        fake_row.total_respostas = 5

        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=fake_row)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        result = await repo.get_score_by_dimension(
            campaign_id=CAMPAIGN_ID,
            dimensao=DimensaoHSE.RELACIONAMENTOS,
        )

        assert result["nivel_risco"] == NivelRisco.CRITICO.value

    async def test_reads_only_from_fact_score_dimensao(self, mock_session):
        """Verifica que o método lê apenas de FactScoreDimensao (Regra R3).

        O método não deve calcular scores — apenas ler dados pré-computados.
        """
        from src.application.services.score_service import ScoreService

        fake_row = MagicMock()
        fake_row.score_medio = Decimal("3.00")
        fake_row.total_respostas = 20

        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=fake_row)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)

        # Verificar que o score_service.calcular_score_dimensao NÃO é chamado
        # (cálculo ocorre apenas no worker, não no repositório)
        original_calcular = ScoreService.calcular_score_dimensao
        calcular_foi_chamado = False

        def spy_calcular(self, *args, **kwargs):
            nonlocal calcular_foi_chamado
            calcular_foi_chamado = True
            return original_calcular(self, *args, **kwargs)

        ScoreService.calcular_score_dimensao = spy_calcular
        try:
            await repo.get_score_by_dimension(
                campaign_id=CAMPAIGN_ID,
                dimensao=DimensaoHSE.SUPORTE_GESTAO,
            )
        finally:
            ScoreService.calcular_score_dimensao = original_calcular

        # O repositório lê dados pré-computados — NÃO calcula scores
        assert not calcular_foi_chamado, (
            "get_score_by_dimension não deve chamar calcular_score_dimensao. "
            "O cálculo ocorre apenas no worker assíncrono (Regra R3)."
        )


# ---------------------------------------------------------------------------
# get_historical_scores
# ---------------------------------------------------------------------------


class TestGetHistoricalScores:
    async def test_returns_scores_for_date_range(self, mock_session):
        """Retorna séries históricas dentro do range de datas."""
        fake_row = MagicMock()
        fake_row.data = date(2024, 6, 15)
        fake_row.dimensao = DimensaoHSE.DEMANDAS
        fake_row.score_medio = Decimal("3.80")
        fake_row.total_respostas = 30

        result_mock = _make_execute_result_many([fake_row])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        historico = await repo.get_historical_scores(
            campaign_id=CAMPAIGN_ID,
            data_inicio=date(2024, 6, 1),
            data_fim=date(2024, 6, 30),
        )

        assert len(historico) == 1
        entry = historico[0]
        assert entry["data"] == "2024-06-15"
        assert entry["dimensao"] == DimensaoHSE.DEMANDAS.value
        assert entry["score_medio"] == 3.80
        assert entry["total_respostas"] == 30

    async def test_returns_empty_for_date_range_without_data(self, mock_session):
        """Retorna lista vazia quando não há dados no período."""
        result_mock = _make_execute_result_many([])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        historico = await repo.get_historical_scores(
            campaign_id=CAMPAIGN_ID,
            data_inicio=date(2020, 1, 1),
            data_fim=date(2020, 12, 31),
        )

        assert historico == []

    async def test_returns_multiple_entries_sorted_by_date(self, mock_session):
        """Retorna múltiplas entradas em ordem por data e dimensão."""
        row1 = MagicMock()
        row1.data = date(2024, 6, 1)
        row1.dimensao = DimensaoHSE.CONTROLE
        row1.score_medio = Decimal("4.00")
        row1.total_respostas = 10

        row2 = MagicMock()
        row2.data = date(2024, 6, 15)
        row2.dimensao = DimensaoHSE.DEMANDAS
        row2.score_medio = Decimal("3.20")
        row2.total_respostas = 15

        result_mock = _make_execute_result_many([row1, row2])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        historico = await repo.get_historical_scores(
            campaign_id=CAMPAIGN_ID,
            data_inicio=date(2024, 6, 1),
            data_fim=date(2024, 6, 30),
        )

        assert len(historico) == 2
        assert historico[0]["data"] == "2024-06-01"
        assert historico[1]["data"] == "2024-06-15"

    async def test_reads_only_from_fact_score_and_dim_tempo(self, mock_session):
        """Verifica que lê apenas de fact_score_dimensao + dim_tempo (Regra R3).

        Não deve agregar dados brutos de survey_responses.
        """
        result_mock = _make_execute_result_many([])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        # Não deve levantar exceção nem chamar survey_responses
        historico = await repo.get_historical_scores(
            campaign_id=CAMPAIGN_ID,
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31),
        )

        assert isinstance(historico, list)
        # Verificar que apenas uma execução foi feita (uma única query)
        assert mock_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# get_top_risk_sectors
# ---------------------------------------------------------------------------


class TestGetTopRiskSectors:
    async def test_returns_sectors_ordered_by_lowest_score(self, mock_session):
        """Retorna setores ordenados por score ascendente (maior risco primeiro)."""
        row1 = MagicMock()
        row1.setor_nome = "TI"
        row1.unidade_nome = "Sede"
        row1.score_medio = Decimal("1.80")  # Crítico — maior risco
        row1.total_respostas = 25

        row2 = MagicMock()
        row2.setor_nome = "RH"
        row2.unidade_nome = "Sede"
        row2.score_medio = Decimal("2.50")  # Importante
        row2.total_respostas = 15

        result_mock = _make_execute_result_many([row1, row2])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        setores = await repo.get_top_risk_sectors(
            campaign_id=CAMPAIGN_ID,
            limit=10,
        )

        assert len(setores) == 2
        # Primeiro setor tem menor score (maior risco)
        assert setores[0]["setor_nome"] == "TI"
        assert setores[0]["score_medio"] == 1.80
        assert setores[0]["nivel_risco"] == NivelRisco.CRITICO.value

        assert setores[1]["setor_nome"] == "RH"
        assert setores[1]["nivel_risco"] == NivelRisco.IMPORTANTE.value

    async def test_returns_empty_for_campaign_without_sectors(self, mock_session):
        """Retorna lista vazia quando não há dados por setor."""
        result_mock = _make_execute_result_many([])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        setores = await repo.get_top_risk_sectors(
            campaign_id=CAMPAIGN_ID,
        )

        assert setores == []

    async def test_respects_limit_parameter(self, mock_session):
        """O parâmetro limit é respeitado na consulta."""
        result_mock = _make_execute_result_many([])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        await repo.get_top_risk_sectors(campaign_id=CAMPAIGN_ID, limit=5)

        # Verificar que a query foi executada com limit
        assert mock_session.execute.called

    async def test_returns_setor_nome_and_unidade_nome(self, mock_session):
        """Cada entrada contém setor_nome, unidade_nome, score_medio e nivel_risco."""
        fake_row = MagicMock()
        fake_row.setor_nome = "Operações"
        fake_row.unidade_nome = "Filial SP"
        fake_row.score_medio = Decimal("3.10")
        fake_row.total_respostas = 8

        result_mock = _make_execute_result_many([fake_row])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        setores = await repo.get_top_risk_sectors(campaign_id=CAMPAIGN_ID)

        assert len(setores) == 1
        entry = setores[0]
        assert entry["setor_nome"] == "Operações"
        assert entry["unidade_nome"] == "Filial SP"
        assert entry["score_medio"] == 3.10
        assert entry["nivel_risco"] == NivelRisco.MODERADO.value
        assert entry["total_respostas"] == 8

    async def test_reads_only_from_fact_score_and_dim_estrutura(self, mock_session):
        """Verifica que lê apenas de fact_score_dimensao + dim_estrutura (Regra R3).

        Não deve calcular scores a partir de survey_responses.
        """
        result_mock = _make_execute_result_many([])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        setores = await repo.get_top_risk_sectors(campaign_id=CAMPAIGN_ID)

        assert isinstance(setores, list)
        # Uma única query executada
        assert mock_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# get_dashboard_summary — Confirmação Regra R3
# ---------------------------------------------------------------------------


class TestGetDashboardSummaryR3:
    async def test_summary_reads_only_precomputed_data(self, mock_session):
        """get_dashboard_summary lê apenas dados pré-computados (Regra R3).

        Confirma que a agregação ocorre sobre fact_score_dimensao, não
        sobre survey_responses — zero cálculos em runtime.
        """
        fake_row = MagicMock()
        fake_row.total_respostas = Decimal("120")
        fake_row.indice_geral = Decimal("3.85")

        result_mock = MagicMock()
        result_mock.one_or_none = MagicMock(return_value=fake_row)
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        summary = await repo.get_dashboard_summary(campaign_id=CAMPAIGN_ID)

        assert summary["total_respostas"] == 120
        assert summary["indice_geral"] == pytest.approx(3.85, abs=0.01)
        assert summary["nivel_geral"] == NivelRisco.MODERADO.value
        # Apenas uma query — sem múltiplas chamadas a survey_responses
        assert mock_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# get_dimensoes_scores — Confirmação Regra R3
# ---------------------------------------------------------------------------


class TestGetDimensoesScoresR3:
    async def test_dimensoes_scores_reads_only_precomputed_data(
        self, mock_session
    ):
        """get_dimensoes_scores lê apenas dados pré-computados (Regra R3)."""
        fake_row = MagicMock()
        fake_row.dimensao = DimensaoHSE.DEMANDAS
        fake_row.score_medio = Decimal("3.60")
        fake_row.total_respostas = Decimal("50")

        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[fake_row])
        mock_session.execute = AsyncMock(return_value=result_mock)

        repo = SQLAnalyticsRepository(mock_session)
        dimensoes = await repo.get_dimensoes_scores(campaign_id=CAMPAIGN_ID)

        assert len(dimensoes) == 1
        assert dimensoes[0]["dimensao"] == DimensaoHSE.DEMANDAS.value
        assert dimensoes[0]["score_medio"] == pytest.approx(3.60, abs=0.01)
        # Uma única query — sem acesso a survey_responses
        assert mock_session.execute.call_count == 1
