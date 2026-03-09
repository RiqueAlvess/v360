"""Testes de integração do action_plan_router — Blueprint 08.

Cobre:
    - GET    /api/v1/action-plans/{campaign_id}               — lista com paginação
    - POST   /api/v1/action-plans/{campaign_id}               — cria plano
    - GET    /api/v1/action-plans/{campaign_id}/{plan_id}     — detalhe
    - PATCH  /api/v1/action-plans/{campaign_id}/{plan_id}     — atualização parcial
    - PATCH  /api/v1/action-plans/{campaign_id}/{plan_id}/status — muda status
    - DELETE /api/v1/action-plans/{campaign_id}/{plan_id}     — soft delete
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
PLAN_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def _make_fake_plan(status: str = "pendente"):
    from src.domain.enums.action_plan_status import ActionPlanStatus
    from src.domain.enums.nivel_risco import NivelRisco

    plan = MagicMock()
    plan.id = PLAN_ID
    plan.company_id = COMPANY_ID
    plan.campaign_id = CAMPAIGN_ID
    plan.titulo = "Reduzir sobrecarga de trabalho"
    plan.descricao = "Ação para reduzir horas extras excessivas no setor de TI"
    plan.status = ActionPlanStatus(status)
    plan.nivel_risco = NivelRisco.CRITICO
    plan.prazo = date(2024, 12, 31)
    plan.dimensao = "demandas"
    plan.unidade_id = None
    plan.setor_id = None
    plan.responsavel_id = None
    plan.responsavel_externo = None
    plan.concluido_em = None
    plan.created_by = USER_ID
    plan.created_at = datetime.now(tz=timezone.utc)
    plan.updated_at = datetime.now(tz=timezone.utc)
    return plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def ap_client(fake_current_user, mock_session):
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
# GET /api/v1/action-plans/{campaign_id}
# ---------------------------------------------------------------------------


class TestListActionPlans:
    async def test_list_action_plans_returns_200(self, ap_client):
        """GET /action-plans/{campaign_id} retorna 200 com paginação e resumo."""
        fake_plans = [_make_fake_plan()]

        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.list_by_campaign",
                new=AsyncMock(return_value=(fake_plans, 1)),
            ),
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.get_resumo_por_status",
                new=AsyncMock(
                    return_value={
                        "total": 1,
                        "por_status": {"pendente": 1, "em_andamento": 0, "concluido": 0, "cancelado": 0},
                    }
                ),
            ),
        ):
            response = await ap_client.get(f"/api/v1/action-plans/{CAMPAIGN_ID}")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "resumo" in data
        assert "pagination" in data

    async def test_list_action_plans_empty_returns_200(self, ap_client):
        """GET /action-plans/{campaign_id} sem planos retorna 200 com lista vazia."""
        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.list_by_campaign",
                new=AsyncMock(return_value=([], 0)),
            ),
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.get_resumo_por_status",
                new=AsyncMock(
                    return_value={"total": 0, "por_status": {}}
                ),
            ),
        ):
            response = await ap_client.get(f"/api/v1/action-plans/{CAMPAIGN_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    async def test_list_action_plans_with_status_filter(self, ap_client):
        """GET /action-plans/{campaign_id}?status=pendente filtra por status."""
        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.list_by_campaign",
                new=AsyncMock(return_value=([], 0)),
            ),
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.get_resumo_por_status",
                new=AsyncMock(
                    return_value={"total": 0, "por_status": {}}
                ),
            ),
        ):
            response = await ap_client.get(
                f"/api/v1/action-plans/{CAMPAIGN_ID}?status=pendente"
            )

        assert response.status_code == 200

    async def test_list_action_plans_requires_authentication(self, mock_session):
        """GET /action-plans/{campaign_id} sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(f"/api/v1/action-plans/{CAMPAIGN_ID}")
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/action-plans/{campaign_id}
# ---------------------------------------------------------------------------


class TestCreateActionPlan:
    async def test_create_action_plan_returns_201(self, ap_client):
        """POST /action-plans/{campaign_id} cria plano e retorna 201."""
        fake_plan = _make_fake_plan()

        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.create",
                new=AsyncMock(return_value=fake_plan),
            ),
            patch(
                "src.infrastructure.queue.task_service.TaskService.enqueue",
                new=AsyncMock(),
            ),
        ):
            response = await ap_client.post(
                f"/api/v1/action-plans/{CAMPAIGN_ID}",
                json={
                    "titulo": "Reduzir sobrecarga de trabalho",
                    "descricao": "Ação para reduzir horas extras excessivas no setor",
                    "nivel_risco": "critico",
                    "prazo": "2024-12-31",
                },
            )

        assert response.status_code == 201

    async def test_create_action_plan_missing_required_fields_returns_422(
        self, ap_client
    ):
        """POST /action-plans sem campos obrigatórios retorna 422."""
        response = await ap_client.post(
            f"/api/v1/action-plans/{CAMPAIGN_ID}",
            json={"titulo": "Só título, sem o resto"},
        )

        assert response.status_code == 422

    async def test_create_action_plan_titulo_too_short_returns_422(self, ap_client):
        """POST /action-plans com título muito curto retorna 422."""
        response = await ap_client.post(
            f"/api/v1/action-plans/{CAMPAIGN_ID}",
            json={
                "titulo": "AB",  # min_length=3
                "descricao": "Ação para reduzir horas extras excessivas no setor",
                "nivel_risco": "critico",
                "prazo": "2024-12-31",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/action-plans/{campaign_id}/{plan_id}/status
# ---------------------------------------------------------------------------


class TestUpdateActionPlanStatus:
    async def test_update_status_returns_200(self, ap_client):
        """PATCH /action-plans/{campaign_id}/{plan_id}/status retorna 200."""
        fake_plan = _make_fake_plan(status="em_andamento")

        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.get_by_id",
                new=AsyncMock(return_value=fake_plan),
            ),
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.update_status",
                new=AsyncMock(return_value=fake_plan),
            ),
            patch(
                "src.infrastructure.queue.task_service.TaskService.enqueue",
                new=AsyncMock(),
            ),
        ):
            response = await ap_client.patch(
                f"/api/v1/action-plans/{CAMPAIGN_ID}/{PLAN_ID}/status",
                json={"status": "em_andamento"},
            )

        assert response.status_code == 200

    async def test_update_status_invalid_status_returns_422(self, ap_client):
        """PATCH /status com status inválido retorna 422."""
        response = await ap_client.patch(
            f"/api/v1/action-plans/{CAMPAIGN_ID}/{PLAN_ID}/status",
            json={"status": "status_invalido"},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/action-plans/{campaign_id}/{plan_id}
# ---------------------------------------------------------------------------


class TestDeleteActionPlan:
    async def test_delete_action_plan_returns_204(self, ap_client):
        """DELETE /action-plans/{campaign_id}/{plan_id} retorna 204 (soft delete)."""
        fake_plan = _make_fake_plan(status="pendente")
        cancelled_plan = _make_fake_plan(status="cancelado")

        with (
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.get_by_id",
                new=AsyncMock(return_value=fake_plan),
            ),
            patch(
                "src.infrastructure.repositories.action_plan_repository.SQLActionPlanRepository.update_status",
                new=AsyncMock(return_value=cancelled_plan),
            ),
        ):
            response = await ap_client.delete(
                f"/api/v1/action-plans/{CAMPAIGN_ID}/{PLAN_ID}"
            )

        assert response.status_code == 204
