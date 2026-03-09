"""Testes de integração do ai_analysis_router — Blueprint 07.

Cobre:
    - POST /api/v1/ai-analyses/request → enfileira análise (HTTP 202)
    - GET  /api/v1/ai-analyses/{id}    → retorna status/resultado
    - GET  /api/v1/ai-analyses/{id} quando análise não existe → 404
    - GET  /api/v1/ai-analyses        → lista com paginação
    - GET  /api/v1/ai-analyses/{id}/summary → resumo agregado
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
ANALYSIS_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _make_fake_analysis(status: str = "pending", tipo: str = "sentimento"):
    analysis = MagicMock()
    analysis.id = ANALYSIS_ID
    analysis.company_id = COMPANY_ID
    analysis.campaign_id = CAMPAIGN_ID
    analysis.setor_id = None
    analysis.dimensao = None
    analysis.tipo = tipo
    analysis.status = status
    analysis.model_usado = None
    analysis.tokens_input = None
    analysis.tokens_output = None
    analysis.resultado = None
    analysis.erro = None
    analysis.prompt_versao = None
    analysis.created_at = datetime.now(tz=timezone.utc)
    analysis.updated_at = datetime.now(tz=timezone.utc)
    return analysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ai_analysis_client(fake_current_user, mock_session):
    """Client HTTP para testes do router de análise de IA."""
    from httpx import ASGITransport, AsyncClient
    from src.infrastructure.database.session import get_db
    from src.main import app
    from src.presentation.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_db] = lambda: mock_session

    import asyncio

    async def _client():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client

    return _client


@pytest.fixture
async def ai_client(fake_current_user, mock_session):
    from httpx import ASGITransport, AsyncClient
    from src.infrastructure.database.session import get_db
    from src.main import app
    from src.presentation.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/ai-analyses/request
# ---------------------------------------------------------------------------


class TestRequestAnalysis:
    async def test_request_analysis_returns_202_accepted(self, ai_client):
        """POST /request enfileira análise e retorna 202 com analysis_id."""
        fake_analysis = _make_fake_analysis(status="pending")

        with (
            patch(
                "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.create",
                new=AsyncMock(return_value=fake_analysis),
            ),
            patch(
                "src.infrastructure.queue.task_service.TaskService.enqueue",
                new=AsyncMock(),
            ),
        ):
            response = await ai_client.post(
                "/api/v1/ai-analyses/request",
                json={
                    "campaign_id": str(CAMPAIGN_ID),
                    "tipo": "sentimento",
                },
            )

        assert response.status_code == 202
        data = response.json()
        assert "analysis_id" in data
        assert data["status"] == "pending"

    async def test_request_analysis_invalid_tipo_returns_422(self, ai_client):
        """POST /request com tipo inválido retorna 422."""
        response = await ai_client.post(
            "/api/v1/ai-analyses/request",
            json={
                "campaign_id": str(CAMPAIGN_ID),
                "tipo": "tipo_invalido",
            },
        )

        assert response.status_code == 422

    async def test_request_analysis_requires_authentication(self, mock_session):
        """POST /request sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/v1/ai-analyses/request",
                    json={"campaign_id": str(CAMPAIGN_ID), "tipo": "sentimento"},
                )

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_request_analysis_with_optional_fields(self, ai_client):
        """POST /request com setor_id e dimensao retorna 202."""
        fake_analysis = _make_fake_analysis()
        setor_id = uuid.uuid4()

        with (
            patch(
                "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.create",
                new=AsyncMock(return_value=fake_analysis),
            ),
            patch(
                "src.infrastructure.queue.task_service.TaskService.enqueue",
                new=AsyncMock(),
            ),
        ):
            response = await ai_client.post(
                "/api/v1/ai-analyses/request",
                json={
                    "campaign_id": str(CAMPAIGN_ID),
                    "tipo": "diagnostico",
                    "setor_id": str(setor_id),
                    "dimensao": "demandas",
                },
            )

        assert response.status_code == 202


# ---------------------------------------------------------------------------
# GET /api/v1/ai-analyses/{analysis_id}
# ---------------------------------------------------------------------------


class TestGetAnalysis:
    async def test_get_analysis_exists_returns_200(self, ai_client):
        """GET /{id} com análise existente da empresa retorna 200."""
        fake_analysis = _make_fake_analysis(status="completed")

        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_id",
            new=AsyncMock(return_value=fake_analysis),
        ):
            response = await ai_client.get(f"/api/v1/ai-analyses/{ANALYSIS_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    async def test_get_analysis_not_found_returns_404(self, ai_client):
        """GET /{id} com análise inexistente retorna 404."""
        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ):
            response = await ai_client.get(f"/api/v1/ai-analyses/{uuid.uuid4()}")

        assert response.status_code == 404

    async def test_get_analysis_other_company_returns_404(self, ai_client):
        """GET /{id} com análise de outra empresa retorna 404."""
        other_company = uuid.UUID("99999999-9999-9999-9999-999999999999")
        fake_analysis = _make_fake_analysis()
        fake_analysis.company_id = other_company

        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_id",
            new=AsyncMock(return_value=fake_analysis),
        ):
            response = await ai_client.get(f"/api/v1/ai-analyses/{ANALYSIS_ID}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/ai-analyses (listagem)
# ---------------------------------------------------------------------------


class TestListAnalyses:
    async def test_list_analyses_returns_200_with_pagination(self, ai_client):
        """GET /ai-analyses?campaign_id={id} retorna 200 com paginação."""
        fake_items = [_make_fake_analysis() for _ in range(2)]

        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_campaign",
            new=AsyncMock(return_value=(fake_items, 2)),
        ):
            response = await ai_client.get(
                f"/api/v1/ai-analyses?campaign_id={CAMPAIGN_ID}"
            )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["total"] == 2

    async def test_list_analyses_empty_returns_200(self, ai_client):
        """GET /ai-analyses sem análises retorna 200 com lista vazia."""
        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_campaign",
            new=AsyncMock(return_value=([], 0)),
        ):
            response = await ai_client.get(
                f"/api/v1/ai-analyses?campaign_id={CAMPAIGN_ID}"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    async def test_list_analyses_missing_campaign_id_returns_422(self, ai_client):
        """GET /ai-analyses sem campaign_id retorna 422."""
        response = await ai_client.get("/api/v1/ai-analyses")
        assert response.status_code == 422

    async def test_list_analyses_with_type_filter(self, ai_client):
        """GET /ai-analyses?tipo=sentimento filtra por tipo."""
        with patch(
            "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_campaign",
            new=AsyncMock(return_value=([], 0)),
        ):
            response = await ai_client.get(
                f"/api/v1/ai-analyses?campaign_id={CAMPAIGN_ID}&tipo=sentimento"
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/ai-analyses/{campaign_id}/summary
# ---------------------------------------------------------------------------


class TestGetAnalysisSummary:
    async def test_get_summary_returns_200(self, ai_client):
        """GET /{campaign_id}/summary retorna 200 com estrutura de resumo."""
        with (
            patch(
                "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_by_campaign",
                new=AsyncMock(return_value=([], 0)),
            ),
            patch(
                "src.infrastructure.repositories.ai_analysis_repository.SQLAiAnalysisRepository.get_completed_by_campaign",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = await ai_client.get(
                f"/api/v1/ai-analyses/{CAMPAIGN_ID}/summary"
            )

        assert response.status_code == 200
        data = response.json()
        assert "total_analyses" in data
        assert "por_setor" in data
        assert "recomendacoes_priorizadas" in data

    async def test_get_summary_requires_authentication(self, mock_session):
        """GET /{campaign_id}/summary sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"/api/v1/ai-analyses/{CAMPAIGN_ID}/summary"
                )
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
