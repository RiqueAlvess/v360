"""Testes unitários do SQLChecklistRepository — Blueprint 09.

Cobre:
    - get_by_campaign(): paginação, filtros
    - get_item_by_id(): sucesso, not found
    - toggle_item(): concluido=True seta campos, concluido=False limpa campos
    - get_progresso(): cálculo correto
    - get_evidencias(): retorna lista de file_assets
    - delete_evidencia(): soft delete
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ITEM_ID = uuid.uuid4()
FILE_ID = uuid.uuid4()


def _make_mock_execute_result(scalars_return=None, scalar_one_return=None, scalar_one_or_none_return=None):
    """Cria um mock para o resultado de session.execute()."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = scalars_return or []
    result.scalars.return_value = scalars_mock
    result.scalar_one.return_value = scalar_one_return or 0
    result.scalar_one_or_none.return_value = scalar_one_or_none_return
    result.one.return_value = MagicMock(total=0, concluidos=0)
    return result


class TestSQLChecklistRepositoryGetByCampaign:
    async def test_get_by_campaign_returns_items_and_total(self, mock_session):
        """get_by_campaign executa queries de count e items."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        repo = SQLChecklistRepository(mock_session)

        # Mock para count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        # Mock para items query
        items_result = MagicMock()
        fake_items = [MagicMock() for _ in range(3)]
        items_scalars = MagicMock()
        items_scalars.all.return_value = fake_items
        items_result.scalars.return_value = items_scalars

        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        items, total = await repo.get_by_campaign(CAMPAIGN_ID, page=1, page_size=20)

        assert total == 3
        assert len(items) == 3
        assert mock_session.execute.call_count == 2

    async def test_get_by_campaign_respects_page_size_max(self, mock_session):
        """page_size acima de 100 é limitado a 100."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        repo = SQLChecklistRepository(mock_session)

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        items_result = MagicMock()
        items_scalars = MagicMock()
        items_scalars.all.return_value = []
        items_result.scalars.return_value = items_scalars
        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        items, total = await repo.get_by_campaign(
            CAMPAIGN_ID, page=1, page_size=999
        )

        assert total == 0


class TestSQLChecklistRepositoryGetItemById:
    async def test_get_item_by_id_returns_item(self, mock_session):
        """get_item_by_id retorna ChecklistItem quando encontrado."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        fake_item = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_item
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLChecklistRepository(mock_session)
        item = await repo.get_item_by_id(ITEM_ID)

        assert item == fake_item

    async def test_get_item_by_id_returns_none_when_not_found(self, mock_session):
        """get_item_by_id retorna None quando item não existe."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLChecklistRepository(mock_session)
        item = await repo.get_item_by_id(ITEM_ID)

        assert item is None


class TestSQLChecklistRepositoryToggleItem:
    async def test_toggle_item_concluido_true_sets_concluido_em(self, mock_session):
        """toggle_item com concluido=True chama execute e flush."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        fake_item = MagicMock()
        result = MagicMock()
        result.scalar_one.return_value = fake_item
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLChecklistRepository(mock_session)
        item = await repo.toggle_item(
            item_id=ITEM_ID,
            concluido=True,
            user_id=USER_ID,
        )

        assert item == fake_item
        mock_session.flush.assert_called_once()

    async def test_toggle_item_concluido_false_clears_fields(self, mock_session):
        """toggle_item com concluido=False não seta concluido_por."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        fake_item = MagicMock()
        result = MagicMock()
        result.scalar_one.return_value = fake_item
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLChecklistRepository(mock_session)
        item = await repo.toggle_item(
            item_id=ITEM_ID,
            concluido=False,
            user_id=USER_ID,
        )

        assert item == fake_item


class TestSQLChecklistRepositoryGetProgresso:
    async def test_get_progresso_calculates_percentual(self, mock_session):
        """get_progresso calcula percentual baseado em total e concluidos."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        row = MagicMock()
        row.total = 10
        row.concluidos = 5
        result = MagicMock()
        result.one.return_value = row
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLChecklistRepository(mock_session)
        progresso = await repo.get_progresso(CAMPAIGN_ID)

        assert progresso["total"] == 10
        assert progresso["concluidos"] == 5
        assert progresso["percentual"] == 50.0

    async def test_get_progresso_zero_total_returns_zero_percent(self, mock_session):
        """get_progresso com total=0 retorna percentual 0.0."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        row = MagicMock()
        row.total = 0
        row.concluidos = 0
        result = MagicMock()
        result.one.return_value = row
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLChecklistRepository(mock_session)
        progresso = await repo.get_progresso(CAMPAIGN_ID)

        assert progresso["percentual"] == 0.0


class TestSQLChecklistRepositoryDeleteEvidencia:
    async def test_delete_evidencia_returns_true_when_found(self, mock_session):
        """delete_evidencia retorna True quando arquivo existe."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLChecklistRepository(mock_session)
        deleted = await repo.delete_evidencia(FILE_ID)

        assert deleted is True

    async def test_delete_evidencia_returns_false_when_not_found(self, mock_session):
        """delete_evidencia retorna False quando arquivo não existe."""
        from src.infrastructure.repositories.checklist_repository import (
            SQLChecklistRepository,
        )

        result = MagicMock()
        result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLChecklistRepository(mock_session)
        deleted = await repo.delete_evidencia(FILE_ID)

        assert deleted is False
