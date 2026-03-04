"""Testes unitários do CampaignService.

Cobre:
    - create_campaign(): sucesso, validação de datas
    - get_campaign(): sucesso, not found, isolamento por empresa
    - list_campaigns(): paginação correta
    - close_campaign(): transição de status
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.campaign_service import CampaignService
from src.domain.enums.campaign_status import CampaignStatus
from src.shared.exceptions import NotFoundError, ValidationError


@pytest.fixture
def mock_checklist_service():
    service = AsyncMock()
    service.generate_from_templates = AsyncMock()
    return service


@pytest.fixture
def campaign_service(mock_campaign_repo, mock_checklist_service):
    return CampaignService(
        campaign_repo=mock_campaign_repo,
        checklist_service=mock_checklist_service,
    )


def _make_fake_campaign(
    campaign_id: uuid.UUID = None,
    company_id: uuid.UUID = None,
    status: CampaignStatus = CampaignStatus.DRAFT,
):
    campaign = MagicMock()
    campaign.id = campaign_id or uuid.uuid4()
    campaign.company_id = company_id or uuid.UUID("11111111-1111-1111-1111-111111111111")
    campaign.nome = "Campanha de Teste 2024"
    campaign.status = status
    campaign.data_inicio = date(2024, 1, 1)
    campaign.data_fim = date(2024, 12, 31)
    campaign.created_at = datetime.now(tz=timezone.utc)
    return campaign


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_COMPANY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


# ---------------------------------------------------------------------------
# create_campaign()
# ---------------------------------------------------------------------------


class TestCampaignServiceCreate:
    async def test_create_campaign_success(self, campaign_service, mock_campaign_repo, mock_checklist_service):
        """Criação de campanha válida retorna Campaign com status DRAFT."""
        fake_campaign = _make_fake_campaign()
        mock_campaign_repo.create.return_value = fake_campaign

        result = await campaign_service.create_campaign(
            company_id=COMPANY_ID,
            nome="Campanha NR-1 2024",
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31),
        )

        assert result.id == fake_campaign.id
        mock_campaign_repo.create.assert_called_once()

    async def test_create_campaign_invalid_dates_raises_validation_error(self, campaign_service):
        """data_fim anterior ou igual a data_inicio levanta ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await campaign_service.create_campaign(
                company_id=COMPANY_ID,
                nome="Campanha inválida",
                data_inicio=date(2024, 12, 31),
                data_fim=date(2024, 1, 1),
            )

        assert "data" in exc_info.value.detail.lower()

    async def test_create_campaign_same_day_raises_validation_error(self, campaign_service):
        """data_fim igual a data_inicio levanta ValidationError."""
        same_date = date(2024, 6, 1)

        with pytest.raises(ValidationError):
            await campaign_service.create_campaign(
                company_id=COMPANY_ID,
                nome="Campanha mesma data",
                data_inicio=same_date,
                data_fim=same_date,
            )


# ---------------------------------------------------------------------------
# get_campaign()
# ---------------------------------------------------------------------------


class TestCampaignServiceGet:
    async def test_get_campaign_success(self, campaign_service, mock_campaign_repo):
        """Busca por campanha existente da empresa retorna Campaign."""
        campaign_id = uuid.uuid4()
        fake_campaign = _make_fake_campaign(campaign_id=campaign_id, company_id=COMPANY_ID)
        mock_campaign_repo.get_by_id.return_value = fake_campaign

        result = await campaign_service.get_campaign(campaign_id, COMPANY_ID)

        assert result.id == campaign_id

    async def test_get_campaign_not_found_raises_not_found(self, campaign_service, mock_campaign_repo):
        """Campanha inexistente levanta NotFoundError."""
        mock_campaign_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await campaign_service.get_campaign(uuid.uuid4(), COMPANY_ID)

    async def test_get_campaign_different_company_raises_not_found(
        self, campaign_service, mock_campaign_repo
    ):
        """Campanha de outra empresa levanta NotFoundError (isolamento multi-tenant)."""
        campaign_id = uuid.uuid4()
        # Campanha pertence a outra empresa
        fake_campaign = _make_fake_campaign(campaign_id=campaign_id, company_id=OTHER_COMPANY_ID)
        mock_campaign_repo.get_by_id.return_value = fake_campaign

        with pytest.raises(NotFoundError):
            await campaign_service.get_campaign(campaign_id, COMPANY_ID)


# ---------------------------------------------------------------------------
# list_campaigns()
# ---------------------------------------------------------------------------


class TestCampaignServiceList:
    async def test_list_campaigns_returns_paginated_result(
        self, campaign_service, mock_campaign_repo
    ):
        """Listagem retorna items com metadados de paginação."""
        fake_campaigns = [_make_fake_campaign() for _ in range(3)]
        mock_campaign_repo.list_by_company.return_value = (fake_campaigns, 3)

        result = await campaign_service.list_campaigns(COMPANY_ID, page=1, page_size=20)

        assert "items" in result
        assert "pagination" in result
        assert result["pagination"]["total"] == 3
        assert len(result["items"]) == 3

    async def test_list_campaigns_empty_returns_empty_list(
        self, campaign_service, mock_campaign_repo
    ):
        """Listagem sem campanhas retorna lista vazia."""
        mock_campaign_repo.list_by_company.return_value = ([], 0)

        result = await campaign_service.list_campaigns(COMPANY_ID)

        assert result["items"] == []
        assert result["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# close_campaign()
# ---------------------------------------------------------------------------


class TestCampaignServiceClose:
    async def test_close_active_campaign_updates_status(
        self, campaign_service, mock_campaign_repo
    ):
        """Encerrar campanha ACTIVE transita para COMPLETED."""
        campaign_id = uuid.uuid4()
        fake_campaign = _make_fake_campaign(
            campaign_id=campaign_id,
            company_id=COMPANY_ID,
            status=CampaignStatus.ACTIVE,
        )
        closed_campaign = _make_fake_campaign(
            campaign_id=campaign_id,
            company_id=COMPANY_ID,
            status=CampaignStatus.COMPLETED,
        )

        mock_campaign_repo.get_by_id.return_value = fake_campaign
        mock_campaign_repo.update_status.return_value = closed_campaign

        result = await campaign_service.close_campaign(campaign_id, COMPANY_ID)

        assert result.status == CampaignStatus.COMPLETED
        mock_campaign_repo.update_status.assert_called_once()
