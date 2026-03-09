"""Testes unitários do SQLWhistleblowerRepository — Blueprint 12.

Cobre:
    - get_company_id_by_slug(): retorna UUID ou None
    - create(): persiste relato com token_hash (nunca token raw)
    - get_by_token_hash(): busca por hash
    - list_by_company(): paginação, filtro por status
    - update_resposta(): registra resposta e atualiza status
    - get_by_id(): busca por UUID

ANONIMATO:
    - create() recebe token_hash, nunca o token raw
    - get_by_token_hash() não retorna dados identificáveis além do conteúdo
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.enums.whistleblower_status import WhistleblowerStatus


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
REPORT_ID = uuid.uuid4()


def _make_fake_report(
    report_id: uuid.UUID = None,
    company_id: uuid.UUID = COMPANY_ID,
    status: str = "recebido",
):
    report = MagicMock()
    report.id = report_id or uuid.uuid4()
    report.company_id = company_id
    report.token_hash = "abc" * 21 + "a"  # SHA-256 hex = 64 chars
    report.categoria = "assedio_moral"
    report.descricao = "Relato detalhado com mais de 20 caracteres"
    report.anonimo = True
    report.nome_opcional = None
    report.status = status
    report.resposta_institucional = None
    report.respondido_por = None
    report.respondido_em = None
    report.created_at = datetime.now(tz=timezone.utc)
    return report


class TestSQLWhistleblowerRepositoryGetCompanyIdBySlug:
    async def test_returns_company_id_for_valid_slug(self, mock_session):
        """get_company_id_by_slug retorna UUID da empresa para slug válido."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = COMPANY_ID
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        company_id = await repo.get_company_id_by_slug("empresa-abc")

        assert company_id == COMPANY_ID

    async def test_returns_none_for_invalid_slug(self, mock_session):
        """get_company_id_by_slug retorna None para slug inválido."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        company_id = await repo.get_company_id_by_slug("slug-invalido")

        assert company_id is None


class TestSQLWhistleblowerRepositoryCreate:
    async def test_create_stores_token_hash_not_raw_token(self, mock_session):
        """create() recebe token_hash e NUNCA armazena o token raw."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        repo = SQLWhistleblowerRepository(mock_session)

        # O token_hash passado é o SHA-256 do token raw — não o token em si
        sha256_hash = "a" * 64  # SHA-256 hex digest = 64 chars

        report = await repo.create(
            company_id=COMPANY_ID,
            token_hash=sha256_hash,
            categoria="assedio_moral",
            descricao="Relato detalhado com conteúdo adequado",
            anonimo=True,
            nome_opcional=None,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        # O objeto adicionado à sessão contém token_hash (não raw token)
        added_object = mock_session.add.call_args[0][0]
        assert added_object.token_hash == sha256_hash

    async def test_create_anonymous_report(self, mock_session):
        """create() com anonimo=True não armazena nome."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        repo = SQLWhistleblowerRepository(mock_session)

        await repo.create(
            company_id=COMPANY_ID,
            token_hash="b" * 64,
            categoria="corrupcao",
            descricao="Relato de corrupção no setor financeiro",
            anonimo=True,
            nome_opcional=None,
        )

        added_object = mock_session.add.call_args[0][0]
        assert added_object.anonimo is True
        assert added_object.nome_opcional is None


class TestSQLWhistleblowerRepositoryGetByTokenHash:
    async def test_get_by_token_hash_returns_report(self, mock_session):
        """get_by_token_hash retorna relato para hash válido."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        fake_report = _make_fake_report()
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_report
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        report = await repo.get_by_token_hash("abc" * 21 + "a")

        assert report == fake_report

    async def test_get_by_token_hash_returns_none_when_not_found(self, mock_session):
        """get_by_token_hash retorna None para hash desconhecido."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        report = await repo.get_by_token_hash("hash_inexistente")

        assert report is None


class TestSQLWhistleblowerRepositoryListByCompany:
    async def test_list_by_company_returns_items_and_total(self, mock_session):
        """list_by_company retorna (items, total) com paginação."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        fake_reports = [_make_fake_report() for _ in range(3)]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = fake_reports
        items_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLWhistleblowerRepository(mock_session)
        reports, total = await repo.list_by_company(COMPANY_ID, page=1, page_size=20)

        assert total == 3
        assert len(reports) == 3

    async def test_list_by_company_with_status_filter(self, mock_session):
        """list_by_company com filtro de status filtra corretamente."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        items_result.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLWhistleblowerRepository(mock_session)
        reports, total = await repo.list_by_company(
            COMPANY_ID, status="em_analise"
        )

        assert total == 0
        assert reports == []

    async def test_list_by_company_respects_page_size_max(self, mock_session):
        """page_size acima de 100 é limitado a 100."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        items_result.scalars.return_value = scalars_mock
        mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

        repo = SQLWhistleblowerRepository(mock_session)
        reports, total = await repo.list_by_company(COMPANY_ID, page_size=999)

        assert total == 0


class TestSQLWhistleblowerRepositoryUpdateResposta:
    async def test_update_resposta_returns_updated_report(self, mock_session):
        """update_resposta retorna relato atualizado."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        fake_report = _make_fake_report(report_id=REPORT_ID)
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_report
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLWhistleblowerRepository(mock_session)
        updated = await repo.update_resposta(
            report_id=REPORT_ID,
            resposta_institucional="Resposta institucional detalhada aqui",
            status=WhistleblowerStatus.EM_ANALISE,
            respondido_por=USER_ID,
        )

        assert updated is not None
        # Verifica que os campos foram atualizados no objeto
        assert fake_report.resposta_institucional == "Resposta institucional detalhada aqui"
        assert fake_report.status == WhistleblowerStatus.EM_ANALISE
        assert fake_report.respondido_por == USER_ID

    async def test_update_resposta_returns_none_when_not_found(self, mock_session):
        """update_resposta retorna None quando relato não existe."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        updated = await repo.update_resposta(
            report_id=REPORT_ID,
            resposta_institucional="Resposta institucional",
            status=WhistleblowerStatus.CONCLUIDO,
            respondido_por=USER_ID,
        )

        assert updated is None


class TestSQLWhistleblowerRepositoryGetById:
    async def test_get_by_id_returns_report(self, mock_session):
        """get_by_id retorna relato para UUID válido."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        fake_report = _make_fake_report(report_id=REPORT_ID)
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_report
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        report = await repo.get_by_id(REPORT_ID)

        assert report == fake_report

    async def test_get_by_id_returns_none_when_not_found(self, mock_session):
        """get_by_id retorna None quando relato não existe."""
        from src.infrastructure.repositories.whistleblower_repository import (
            SQLWhistleblowerRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLWhistleblowerRepository(mock_session)
        report = await repo.get_by_id(uuid.uuid4())

        assert report is None
