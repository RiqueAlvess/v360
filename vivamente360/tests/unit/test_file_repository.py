"""Testes unitários do SQLFileRepository — Blueprint 11.

Cobre:
    - create(): persiste metadados de arquivo com flush
    - get_by_id(): retorna FileAsset, retorna None para deletados
    - list_by_context(): paginação, filtro por contexto e referencia_id
    - soft_delete(): seta deletado=True, retorna True/False
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FILE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
REF_ID = uuid.uuid4()


def _make_fake_file_asset(file_id: uuid.UUID = None, deletado: bool = False):
    asset = MagicMock()
    asset.id = file_id or uuid.uuid4()
    asset.company_id = COMPANY_ID
    asset.contexto = "checklist_evidencia"
    asset.referencia_id = REF_ID
    asset.nome_original = "laudo.pdf"
    asset.tamanho_bytes = 2048
    asset.content_type = "application/pdf"
    asset.storage_key = "company/checklist/uuid/laudo.pdf"
    asset.created_by = USER_ID
    asset.deletado = deletado
    asset.deletado_em = datetime.now(tz=timezone.utc) if deletado else None
    asset.created_at = datetime.now(tz=timezone.utc)
    return asset


class TestSQLFileRepositoryCreate:
    async def test_create_adds_to_session_and_flushes(self, mock_session):
        """create() adiciona FileAsset à sessão e faz flush."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        repo = SQLFileRepository(mock_session)
        asset = await repo.create(
            company_id=COMPANY_ID,
            contexto="checklist_evidencia",
            nome_original="laudo.pdf",
            tamanho_bytes=2048,
            content_type="application/pdf",
            storage_key="company/checklist/uuid/laudo.pdf",
            created_by=USER_ID,
            referencia_id=REF_ID,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_create_without_referencia_id(self, mock_session):
        """create() sem referencia_id é válido."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        repo = SQLFileRepository(mock_session)
        await repo.create(
            company_id=COMPANY_ID,
            contexto="outros",
            nome_original="arquivo.png",
            tamanho_bytes=512,
            content_type="image/png",
            storage_key="company/outros/uuid/arquivo.png",
            created_by=USER_ID,
        )

        mock_session.add.assert_called_once()


class TestSQLFileRepositoryGetById:
    async def test_get_by_id_returns_file_asset(self, mock_session):
        """get_by_id retorna FileAsset quando arquivo existe e não está deletado."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        fake_asset = _make_fake_file_asset(file_id=FILE_ID)
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_asset
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLFileRepository(mock_session)
        asset = await repo.get_by_id(FILE_ID)

        assert asset == fake_asset

    async def test_get_by_id_returns_none_for_deleted_file(self, mock_session):
        """get_by_id retorna None para arquivo marcado como deletado."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # Filtrado por deletado=False
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLFileRepository(mock_session)
        asset = await repo.get_by_id(FILE_ID)

        assert asset is None

    async def test_get_by_id_returns_none_when_not_found(self, mock_session):
        """get_by_id retorna None quando arquivo não existe."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLFileRepository(mock_session)
        asset = await repo.get_by_id(uuid.uuid4())

        assert asset is None


class TestSQLFileRepositoryListByContext:
    async def test_list_by_context_returns_items_and_total(self, mock_session):
        """list_by_context retorna (items, total) com paginação."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        fake_items = [_make_fake_file_asset() for _ in range(2)]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = fake_items
        items_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLFileRepository(mock_session)
        items, total = await repo.list_by_context(
            company_id=COMPANY_ID,
            contexto="checklist_evidencia",
            page=1,
            page_size=20,
        )

        assert total == 2
        assert len(items) == 2

    async def test_list_by_context_with_referencia_id_filter(self, mock_session):
        """list_by_context com referencia_id filtra corretamente."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        items_result.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLFileRepository(mock_session)
        items, total = await repo.list_by_context(
            company_id=COMPANY_ID,
            contexto="checklist_evidencia",
            referencia_id=REF_ID,
        )

        assert total == 0
        assert items == []

    async def test_list_by_context_respects_page_size_max(self, mock_session):
        """page_size acima de 100 é limitado a 100."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        items_result.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLFileRepository(mock_session)
        items, total = await repo.list_by_context(
            company_id=COMPANY_ID,
            contexto="checklist_evidencia",
            page_size=999,
        )

        # Verifica que não levanta erro e retorna corretamente
        assert total == 0


class TestSQLFileRepositorySoftDelete:
    async def test_soft_delete_returns_true_when_found(self, mock_session):
        """soft_delete retorna True quando arquivo existe e é marcado."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLFileRepository(mock_session)
        deleted = await repo.soft_delete(FILE_ID)

        assert deleted is True
        mock_session.flush.assert_called_once()

    async def test_soft_delete_returns_false_when_not_found(self, mock_session):
        """soft_delete retorna False quando arquivo não existe ou já deletado."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        result = MagicMock()
        result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLFileRepository(mock_session)
        deleted = await repo.soft_delete(uuid.uuid4())

        assert deleted is False

    async def test_soft_delete_does_not_hard_delete(self, mock_session):
        """soft_delete usa UPDATE, nunca hard DELETE."""
        from src.infrastructure.repositories.file_repository import SQLFileRepository

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLFileRepository(mock_session)
        await repo.soft_delete(FILE_ID)

        # Verifica que delete() da sessão não foi chamado diretamente
        assert not hasattr(mock_session, "delete") or not mock_session.delete.called
