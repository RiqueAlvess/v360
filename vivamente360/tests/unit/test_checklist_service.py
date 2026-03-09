"""Testes unitários do ChecklistService — Blueprint 09.

Cobre:
    - get_checklist(): paginação, filtros por categoria e concluido
    - toggle_item(): sucesso, item inexistente, empresa diferente
    - get_evidencias(): sucesso, item inexistente
    - add_evidencia(): sucesso, item inexistente, empresa diferente
    - delete_evidencia(): sucesso, evidência inexistente
    - create_items_from_templates(): criação em massa
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.checklist_service import ChecklistService
from src.shared.exceptions import ForbiddenError, NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_COMPANY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ITEM_ID = uuid.uuid4()
FILE_ID = uuid.uuid4()


def _make_fake_item(
    item_id: uuid.UUID = None,
    company_id: uuid.UUID = COMPANY_ID,
    campaign_id: uuid.UUID = CAMPAIGN_ID,
    concluido: bool = False,
):
    item = MagicMock()
    item.id = item_id or uuid.uuid4()
    item.company_id = company_id
    item.campaign_id = campaign_id
    item.template_id = uuid.uuid4()
    item.codigo = "NR1.01"
    item.descricao = "Avaliar riscos psicossociais"
    item.categoria = "avaliacao"
    item.obrigatorio = True
    item.prazo_dias = 30
    item.ordem = 1
    item.concluido = concluido
    item.concluido_em = datetime.now(tz=timezone.utc) if concluido else None
    item.concluido_por = USER_ID if concluido else None
    item.observacao = None
    item.prazo = None
    item.created_at = datetime.now(tz=timezone.utc)
    return item


def _make_fake_file_asset(file_id: uuid.UUID = None):
    asset = MagicMock()
    asset.id = file_id or uuid.uuid4()
    asset.nome_original = "evidencia.pdf"
    asset.content_type = "application/pdf"
    asset.tamanho_bytes = 1024
    asset.storage_key = "company/checklist/uuid/evidencia.pdf"
    asset.created_by = USER_ID
    asset.created_at = datetime.now(tz=timezone.utc)
    return asset


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def checklist_service(mock_checklist_repo):
    return ChecklistService(checklist_repo=mock_checklist_repo)


# ---------------------------------------------------------------------------
# get_checklist()
# ---------------------------------------------------------------------------


class TestChecklistServiceGetChecklist:
    async def test_get_checklist_returns_items_and_progress(
        self, checklist_service, mock_checklist_repo
    ):
        """get_checklist retorna items, progresso e paginação."""
        fake_items = [_make_fake_item() for _ in range(5)]
        mock_checklist_repo.get_by_campaign.return_value = (fake_items, 5)
        mock_checklist_repo.get_progresso.return_value = {
            "total": 10,
            "concluidos": 5,
            "percentual": 50.0,
        }

        result = await checklist_service.get_checklist(campaign_id=CAMPAIGN_ID)

        assert "items" in result
        assert "progresso" in result
        assert "pagination" in result
        assert len(result["items"]) == 5
        assert result["progresso"]["percentual"] == 50.0

    async def test_get_checklist_with_categoria_filter(
        self, checklist_service, mock_checklist_repo
    ):
        """Filtro por categoria é repassado ao repositório."""
        mock_checklist_repo.get_by_campaign.return_value = ([], 0)
        mock_checklist_repo.get_progresso.return_value = {
            "total": 0, "concluidos": 0, "percentual": 0.0
        }

        await checklist_service.get_checklist(
            campaign_id=CAMPAIGN_ID,
            categoria="avaliacao",
        )

        call_kwargs = mock_checklist_repo.get_by_campaign.call_args.kwargs
        assert call_kwargs.get("categoria") == "avaliacao"

    async def test_get_checklist_with_concluido_filter(
        self, checklist_service, mock_checklist_repo
    ):
        """Filtro por concluido é repassado ao repositório."""
        mock_checklist_repo.get_by_campaign.return_value = ([], 0)
        mock_checklist_repo.get_progresso.return_value = {
            "total": 0, "concluidos": 0, "percentual": 0.0
        }

        await checklist_service.get_checklist(
            campaign_id=CAMPAIGN_ID,
            concluido=True,
        )

        call_kwargs = mock_checklist_repo.get_by_campaign.call_args.kwargs
        assert call_kwargs.get("concluido") is True

    async def test_get_checklist_empty_returns_zero_progress(
        self, checklist_service, mock_checklist_repo
    ):
        """Checklist vazio retorna progresso zerado."""
        mock_checklist_repo.get_by_campaign.return_value = ([], 0)
        mock_checklist_repo.get_progresso.return_value = {
            "total": 0, "concluidos": 0, "percentual": 0.0
        }

        result = await checklist_service.get_checklist(campaign_id=CAMPAIGN_ID)

        assert result["items"] == []
        assert result["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# toggle_item()
# ---------------------------------------------------------------------------


class TestChecklistServiceToggleItem:
    async def test_toggle_item_to_concluido(
        self, checklist_service, mock_checklist_repo
    ):
        """toggle_item com concluido=True atualiza o item."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        updated_item = _make_fake_item(item_id=ITEM_ID, concluido=True)
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.toggle_item.return_value = updated_item

        result = await checklist_service.toggle_item(
            item_id=ITEM_ID,
            concluido=True,
            user_id=USER_ID,
            company_id=COMPANY_ID,
        )

        assert result.concluido is True
        mock_checklist_repo.toggle_item.assert_called_once()

    async def test_toggle_item_not_found_raises_not_found(
        self, checklist_service, mock_checklist_repo
    ):
        """Item inexistente levanta NotFoundError."""
        mock_checklist_repo.get_item_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await checklist_service.toggle_item(
                item_id=ITEM_ID,
                concluido=True,
                user_id=USER_ID,
                company_id=COMPANY_ID,
            )

    async def test_toggle_item_other_company_raises_forbidden(
        self, checklist_service, mock_checklist_repo
    ):
        """Item de outra empresa levanta ForbiddenError."""
        fake_item = _make_fake_item(company_id=OTHER_COMPANY_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item

        with pytest.raises(ForbiddenError):
            await checklist_service.toggle_item(
                item_id=ITEM_ID,
                concluido=True,
                user_id=USER_ID,
                company_id=COMPANY_ID,
            )

    async def test_toggle_item_with_observacao(
        self, checklist_service, mock_checklist_repo
    ):
        """toggle_item com observação repassa ao repositório."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.toggle_item.return_value = fake_item

        await checklist_service.toggle_item(
            item_id=ITEM_ID,
            concluido=True,
            user_id=USER_ID,
            company_id=COMPANY_ID,
            observacao="Ação realizada em reunião",
        )

        call_kwargs = mock_checklist_repo.toggle_item.call_args.kwargs
        assert call_kwargs.get("observacao") == "Ação realizada em reunião"


# ---------------------------------------------------------------------------
# get_evidencias()
# ---------------------------------------------------------------------------


class TestChecklistServiceGetEvidencias:
    async def test_get_evidencias_success(
        self, checklist_service, mock_checklist_repo
    ):
        """get_evidencias retorna lista de FileAssets."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        fake_files = [_make_fake_file_asset() for _ in range(2)]
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.get_evidencias.return_value = fake_files

        result = await checklist_service.get_evidencias(
            item_id=ITEM_ID, company_id=COMPANY_ID
        )

        assert len(result) == 2

    async def test_get_evidencias_item_not_found_raises_not_found(
        self, checklist_service, mock_checklist_repo
    ):
        """Item inexistente levanta NotFoundError."""
        mock_checklist_repo.get_item_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await checklist_service.get_evidencias(
                item_id=ITEM_ID, company_id=COMPANY_ID
            )

    async def test_get_evidencias_other_company_raises_forbidden(
        self, checklist_service, mock_checklist_repo
    ):
        """Item de outra empresa levanta ForbiddenError."""
        fake_item = _make_fake_item(company_id=OTHER_COMPANY_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item

        with pytest.raises(ForbiddenError):
            await checklist_service.get_evidencias(
                item_id=ITEM_ID, company_id=COMPANY_ID
            )


# ---------------------------------------------------------------------------
# add_evidencia()
# ---------------------------------------------------------------------------


class TestChecklistServiceAddEvidencia:
    async def test_add_evidencia_success(
        self, checklist_service, mock_checklist_repo
    ):
        """add_evidencia registra metadados e retorna FileAsset."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        fake_asset = _make_fake_file_asset()
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.add_evidencia.return_value = fake_asset

        result = await checklist_service.add_evidencia(
            item_id=ITEM_ID,
            company_id=COMPANY_ID,
            nome_original="evidencia.pdf",
            tamanho_bytes=1024,
            content_type="application/pdf",
            storage_key="company/checklist/uuid/evidencia.pdf",
        )

        assert result.id == fake_asset.id
        mock_checklist_repo.add_evidencia.assert_called_once()

    async def test_add_evidencia_item_not_found_raises_not_found(
        self, checklist_service, mock_checklist_repo
    ):
        """Item inexistente levanta NotFoundError."""
        mock_checklist_repo.get_item_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await checklist_service.add_evidencia(
                item_id=ITEM_ID,
                company_id=COMPANY_ID,
                nome_original="evidencia.pdf",
                tamanho_bytes=1024,
                content_type="application/pdf",
                storage_key="company/checklist/uuid/evidencia.pdf",
            )

    async def test_add_evidencia_other_company_raises_forbidden(
        self, checklist_service, mock_checklist_repo
    ):
        """Item de outra empresa levanta ForbiddenError."""
        fake_item = _make_fake_item(company_id=OTHER_COMPANY_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item

        with pytest.raises(ForbiddenError):
            await checklist_service.add_evidencia(
                item_id=ITEM_ID,
                company_id=COMPANY_ID,
                nome_original="evidencia.pdf",
                tamanho_bytes=1024,
                content_type="application/pdf",
                storage_key="company/checklist/uuid/evidencia.pdf",
            )


# ---------------------------------------------------------------------------
# delete_evidencia()
# ---------------------------------------------------------------------------


class TestChecklistServiceDeleteEvidencia:
    async def test_delete_evidencia_success(
        self, checklist_service, mock_checklist_repo
    ):
        """delete_evidencia chama soft delete no repositório."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.delete_evidencia.return_value = True

        await checklist_service.delete_evidencia(
            item_id=ITEM_ID,
            file_id=FILE_ID,
            company_id=COMPANY_ID,
        )

        mock_checklist_repo.delete_evidencia.assert_called_once_with(FILE_ID)

    async def test_delete_evidencia_file_not_found_raises_not_found(
        self, checklist_service, mock_checklist_repo
    ):
        """Evidência inexistente levanta NotFoundError."""
        fake_item = _make_fake_item(item_id=ITEM_ID)
        mock_checklist_repo.get_item_by_id.return_value = fake_item
        mock_checklist_repo.delete_evidencia.return_value = False

        with pytest.raises(NotFoundError):
            await checklist_service.delete_evidencia(
                item_id=ITEM_ID,
                file_id=FILE_ID,
                company_id=COMPANY_ID,
            )


# ---------------------------------------------------------------------------
# create_items_from_templates()
# ---------------------------------------------------------------------------


class TestChecklistServiceCreateItemsFromTemplates:
    async def test_create_items_from_templates_returns_items(
        self, checklist_service, mock_checklist_repo
    ):
        """create_items_from_templates delega ao repositório e retorna itens."""
        fake_items = [_make_fake_item() for _ in range(10)]
        mock_checklist_repo.create_items_from_templates.return_value = fake_items

        result = await checklist_service.create_items_from_templates(
            campaign_id=CAMPAIGN_ID,
            company_id=COMPANY_ID,
        )

        assert len(result) == 10
        mock_checklist_repo.create_items_from_templates.assert_called_once_with(
            campaign_id=CAMPAIGN_ID,
            company_id=COMPANY_ID,
        )

    async def test_create_items_from_templates_empty_returns_empty(
        self, checklist_service, mock_checklist_repo
    ):
        """Sem templates retorna lista vazia."""
        mock_checklist_repo.create_items_from_templates.return_value = []

        result = await checklist_service.create_items_from_templates(
            campaign_id=CAMPAIGN_ID,
            company_id=COMPANY_ID,
        )

        assert result == []
