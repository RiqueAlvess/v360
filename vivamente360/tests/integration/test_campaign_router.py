"""Testes de integração do campaign_router.

Testa os endpoints autenticados de campanhas:
    - GET  /api/v1/campaigns
    - POST /api/v1/campaigns
    - GET  /api/v1/campaigns/{id}
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _make_fake_campaign(status: str = "draft"):
    from src.domain.enums.campaign_status import CampaignStatus

    campaign = MagicMock()
    campaign.id = CAMPAIGN_ID
    campaign.company_id = COMPANY_ID
    campaign.nome = "Campanha de Teste 2024"
    campaign.status = CampaignStatus(status)
    campaign.data_inicio = date(2024, 1, 1)
    campaign.data_fim = date(2024, 12, 31)
    campaign.created_at = datetime.now(tz=timezone.utc)
    campaign.updated_at = datetime.now(tz=timezone.utc)
    return campaign


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def campaigns_test_app(fake_current_user, mock_session):
    """App com autenticação e sessão mockadas."""
    from src.infrastructure.database.session import get_db
    from src.main import app
    from src.presentation.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_db] = lambda: mock_session

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def campaigns_client(campaigns_test_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=campaigns_test_app),
        base_url="http://testserver",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# GET /api/v1/campaigns
# ---------------------------------------------------------------------------


class TestListCampaigns:
    async def test_list_campaigns_returns_200(self, campaigns_client):
        """Listagem de campanhas autenticada retorna HTTP 200."""
        with patch(
            "src.infrastructure.repositories.campaign_repository.SQLCampaignRepository.list_by_company",
            new=AsyncMock(return_value=([_make_fake_campaign()], 1)),
        ):
            response = await campaigns_client.get("/api/v1/campaigns")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data

    async def test_list_campaigns_empty_returns_200(self, campaigns_client):
        """Listagem sem campanhas retorna HTTP 200 com lista vazia."""
        with patch(
            "src.infrastructure.repositories.campaign_repository.SQLCampaignRepository.list_by_company",
            new=AsyncMock(return_value=([], 0)),
        ):
            response = await campaigns_client.get("/api/v1/campaigns")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["pagination"]["total"] == 0

    async def test_list_campaigns_without_auth_returns_401(self, mock_session):
        """Listagem sem autenticação retorna HTTP 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/api/v1/campaigns")

            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/campaigns
# ---------------------------------------------------------------------------


class TestCreateCampaign:
    async def test_create_campaign_success_returns_201(self, campaigns_client):
        """Criação válida de campanha retorna HTTP 201."""
        fake_campaign = _make_fake_campaign()

        with (
            patch(
                "src.infrastructure.repositories.campaign_repository.SQLCampaignRepository.create",
                new=AsyncMock(return_value=fake_campaign),
            ),
            patch(
                "src.infrastructure.repositories.checklist_repository.SQLChecklistRepository.bulk_create_from_templates",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "src.infrastructure.repositories.checklist_repository.SQLChecklistRepository.get_active_templates",
                new=AsyncMock(return_value=[]),
            ),
        ):
            response = await campaigns_client.post(
                "/api/v1/campaigns",
                json={
                    "nome": "Campanha NR-1 2024",
                    "data_inicio": "2024-01-01",
                    "data_fim": "2024-12-31",
                },
            )

        assert response.status_code == 201

    async def test_create_campaign_invalid_dates_returns_422(self, campaigns_client):
        """Criação com data_fim anterior retorna HTTP 422."""
        response = await campaigns_client.post(
            "/api/v1/campaigns",
            json={
                "nome": "Campanha inválida",
                "data_inicio": "2024-12-31",
                "data_fim": "2024-01-01",
            },
        )

        assert response.status_code in (400, 422)

    async def test_create_campaign_missing_nome_returns_422(self, campaigns_client):
        """Criação sem nome retorna HTTP 422."""
        response = await campaigns_client.post(
            "/api/v1/campaigns",
            json={
                "data_inicio": "2024-01-01",
                "data_fim": "2024-12-31",
            },
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/campaigns/{id}
# ---------------------------------------------------------------------------


class TestGetCampaign:
    async def test_get_campaign_exists_returns_200(self, campaigns_client):
        """Busca de campanha existente retorna HTTP 200."""
        fake_campaign = _make_fake_campaign()

        with patch(
            "src.infrastructure.repositories.campaign_repository.SQLCampaignRepository.get_by_id",
            new=AsyncMock(return_value=fake_campaign),
        ):
            response = await campaigns_client.get(f"/api/v1/campaigns/{CAMPAIGN_ID}")

        assert response.status_code == 200

    async def test_get_campaign_not_found_returns_404(self, campaigns_client):
        """Campanha inexistente retorna HTTP 404."""
        with patch(
            "src.infrastructure.repositories.campaign_repository.SQLCampaignRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ):
            response = await campaigns_client.get(f"/api/v1/campaigns/{uuid.uuid4()}")

        assert response.status_code == 404
