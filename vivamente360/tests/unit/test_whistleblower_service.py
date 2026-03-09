"""Testes unitários do WhistleblowerService — Blueprint 12.

Cobre:
    - submit(): gera token, salva hash SHA-256, nunca persiste token raw
    - consulta(): busca por token_hash, retorna status/resposta
    - list_reports(): paginação, filtro por status
    - get_report(): sucesso, not found, empresa diferente
    - respond(): status válido, status inválido
    - resolve_company_slug(): sucesso, slug inválido
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.whistleblower_service import WhistleblowerService
from src.domain.enums.whistleblower_categoria import WhistleblowerCategoria
from src.domain.enums.whistleblower_status import WhistleblowerStatus
from src.shared.exceptions import NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_COMPANY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
REPORT_ID = uuid.uuid4()


def _make_fake_report(
    report_id: uuid.UUID = None,
    company_id: uuid.UUID = COMPANY_ID,
    status: str = "recebido",
    resposta: str = None,
):
    report = MagicMock()
    report.id = report_id or uuid.uuid4()
    report.company_id = company_id
    report.token_hash = "abc123sha256hash"
    report.categoria = "assedio_moral"
    report.descricao = "Relato detalhado de assédio moral com mais de 20 chars"
    report.anonimo = True
    report.nome_opcional = None
    report.status = status
    report.resposta_institucional = resposta
    report.respondido_por = None
    report.respondido_em = None
    report.created_at = datetime.now(tz=timezone.utc)
    return report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_whistleblower_repo():
    from src.infrastructure.repositories.whistleblower_repository import WhistleblowerRepository

    repo = AsyncMock(spec=WhistleblowerRepository)
    return repo


@pytest.fixture
def mock_task_service():
    from src.infrastructure.queue.task_service import TaskService

    service = AsyncMock(spec=TaskService)
    service.enqueue = AsyncMock()
    return service


@pytest.fixture
def mock_notification_service():
    from src.application.services.notification_service import NotificationService

    service = AsyncMock(spec=NotificationService)
    service.notify = AsyncMock()
    service.notify_by_role = AsyncMock()
    return service


@pytest.fixture
def whistleblower_service(
    mock_whistleblower_repo, mock_task_service, mock_notification_service
):
    return WhistleblowerService(
        repo=mock_whistleblower_repo,
        task_service=mock_task_service,
        notification_service=mock_notification_service,
    )


# ---------------------------------------------------------------------------
# resolve_company_slug()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceResolveSlug:
    async def test_resolve_valid_slug_returns_company_id(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """Slug válido retorna UUID da empresa."""
        mock_whistleblower_repo.get_company_id_by_slug.return_value = COMPANY_ID

        result = await whistleblower_service.resolve_company_slug("empresa-abc")

        assert result == COMPANY_ID

    async def test_resolve_invalid_slug_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """Slug inválido ou empresa inativa levanta NotFoundError."""
        mock_whistleblower_repo.get_company_id_by_slug.return_value = None

        with pytest.raises(NotFoundError):
            await whistleblower_service.resolve_company_slug("slug-invalido")


# ---------------------------------------------------------------------------
# submit()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceSubmit:
    async def test_submit_returns_report_token(
        self, whistleblower_service, mock_whistleblower_repo, mock_task_service
    ):
        """submit() retorna report_token (token raw UMA VEZ)."""
        fake_report = _make_fake_report()
        mock_whistleblower_repo.create.return_value = fake_report

        result = await whistleblower_service.submit(
            company_id=COMPANY_ID,
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="Relato detalhado de assédio moral no departamento",
            nome_opcional=None,
        )

        assert "report_token" in result
        assert len(result["report_token"]) > 0

    async def test_submit_never_stores_raw_token(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """submit() não persiste o token raw — apenas o SHA-256 (token_hash)."""
        fake_report = _make_fake_report()
        mock_whistleblower_repo.create.return_value = fake_report

        result = await whistleblower_service.submit(
            company_id=COMPANY_ID,
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="Relato detalhado de assédio moral no departamento",
            nome_opcional=None,
        )

        # O token raw retornado ao caller não deve ser o que foi salvo no banco
        create_call_kwargs = mock_whistleblower_repo.create.call_args.kwargs
        saved_hash = create_call_kwargs["token_hash"]
        raw_token = result["report_token"]

        # Token raw ≠ hash salvo
        assert raw_token != saved_hash
        # Hash é SHA-256 (64 chars hex)
        assert len(saved_hash) == 64

    async def test_submit_enqueues_admin_notification_task(
        self, whistleblower_service, mock_whistleblower_repo, mock_task_service
    ):
        """submit() enfileira tarefa NOTIFY_WHISTLEBLOWER_ADMIN."""
        from src.domain.enums.task_queue_type import TaskQueueType

        fake_report = _make_fake_report()
        mock_whistleblower_repo.create.return_value = fake_report

        await whistleblower_service.submit(
            company_id=COMPANY_ID,
            categoria=WhistleblowerCategoria.CORRUPCAO,
            descricao="Relato de corrupção com mais de 20 caracteres aqui",
            nome_opcional=None,
        )

        mock_task_service.enqueue.assert_called_once()
        call_kwargs = mock_task_service.enqueue.call_args.kwargs
        assert call_kwargs["tipo"] == TaskQueueType.NOTIFY_WHISTLEBLOWER_ADMIN

    async def test_submit_with_nome_sets_anonimo_false(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """submit() com nome_opcional seta anonimo=False."""
        fake_report = _make_fake_report()
        mock_whistleblower_repo.create.return_value = fake_report

        await whistleblower_service.submit(
            company_id=COMPANY_ID,
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="Relato detalhado com identificação do denunciante",
            nome_opcional="João Silva",
        )

        create_kwargs = mock_whistleblower_repo.create.call_args.kwargs
        assert create_kwargs["anonimo"] is False
        assert create_kwargs["nome_opcional"] == "João Silva"

    async def test_submit_without_nome_sets_anonimo_true(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """submit() sem nome_opcional seta anonimo=True."""
        fake_report = _make_fake_report()
        mock_whistleblower_repo.create.return_value = fake_report

        await whistleblower_service.submit(
            company_id=COMPANY_ID,
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="Relato anônimo detalhado sobre assédio moral",
            nome_opcional=None,
        )

        create_kwargs = mock_whistleblower_repo.create.call_args.kwargs
        assert create_kwargs["anonimo"] is True

    async def test_submit_short_descricao_raises_validation_error(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """Descrição com menos de 20 chars levanta ValidationError."""
        with pytest.raises(ValidationError):
            await whistleblower_service.submit(
                company_id=COMPANY_ID,
                categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
                descricao="Curto",  # < 20 chars
                nome_opcional=None,
            )

        mock_whistleblower_repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# consulta()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceConsulta:
    async def test_consulta_valid_token_returns_status(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """consulta() com token válido retorna status e resposta."""
        fake_report = _make_fake_report(
            status="em_analise",
            resposta="Sua denúncia está sendo analisada.",
        )
        mock_whistleblower_repo.get_by_token_hash.return_value = fake_report

        result = await whistleblower_service.consulta(
            company_id=COMPANY_ID,
            report_token="token_valido_aqui_com_43chars_xxxxxxxxxxxxxxxxxxx",
        )

        assert result["status"] == "em_analise"
        assert "resposta_institucional" in result

    async def test_consulta_invalid_token_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """consulta() com token inválido levanta NotFoundError."""
        mock_whistleblower_repo.get_by_token_hash.return_value = None

        with pytest.raises(NotFoundError):
            await whistleblower_service.consulta(
                company_id=COMPANY_ID,
                report_token="token_invalido",
            )

    async def test_consulta_other_company_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """consulta() com token de outra empresa levanta NotFoundError."""
        fake_report = _make_fake_report(company_id=OTHER_COMPANY_ID)
        mock_whistleblower_repo.get_by_token_hash.return_value = fake_report

        with pytest.raises(NotFoundError):
            await whistleblower_service.consulta(
                company_id=COMPANY_ID,
                report_token="token_da_outra_empresa",
            )


# ---------------------------------------------------------------------------
# list_reports()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceListReports:
    async def test_list_reports_returns_paginated_result(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """list_reports retorna items e pagination."""
        fake_reports = [_make_fake_report() for _ in range(3)]
        mock_whistleblower_repo.list_by_company.return_value = (fake_reports, 3)

        result = await whistleblower_service.list_reports(
            company_id=COMPANY_ID, page=1, page_size=20
        )

        assert "items" in result
        assert "pagination" in result
        assert len(result["items"]) == 3

    async def test_list_reports_empty_returns_zero(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """list_reports sem relatos retorna lista vazia."""
        mock_whistleblower_repo.list_by_company.return_value = ([], 0)

        result = await whistleblower_service.list_reports(company_id=COMPANY_ID)

        assert result["items"] == []
        assert result["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# get_report()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceGetReport:
    async def test_get_report_success(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """get_report retorna relato para empresa correta."""
        fake_report = _make_fake_report(report_id=REPORT_ID)
        mock_whistleblower_repo.get_by_id.return_value = fake_report

        result = await whistleblower_service.get_report(REPORT_ID, COMPANY_ID)

        assert result.id == REPORT_ID

    async def test_get_report_not_found_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """get_report com ID inexistente levanta NotFoundError."""
        mock_whistleblower_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await whistleblower_service.get_report(REPORT_ID, COMPANY_ID)

    async def test_get_report_other_company_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """get_report de outra empresa levanta NotFoundError."""
        fake_report = _make_fake_report(company_id=OTHER_COMPANY_ID)
        mock_whistleblower_repo.get_by_id.return_value = fake_report

        with pytest.raises(NotFoundError):
            await whistleblower_service.get_report(REPORT_ID, COMPANY_ID)


# ---------------------------------------------------------------------------
# respond()
# ---------------------------------------------------------------------------


class TestWhistleblowerServiceRespond:
    async def test_respond_with_valid_status(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """respond() com status válido (em_analise) atualiza relato."""
        updated_report = _make_fake_report(
            report_id=REPORT_ID,
            status="em_analise",
            resposta="Estamos analisando o seu relato.",
        )
        mock_whistleblower_repo.update_resposta.return_value = updated_report

        result = await whistleblower_service.respond(
            report_id=REPORT_ID,
            company_id=COMPANY_ID,
            resposta_institucional="Estamos analisando o seu relato.",
            status=WhistleblowerStatus.EM_ANALISE,
            respondido_por=USER_ID,
        )

        assert result.status == "em_analise"

    async def test_respond_with_status_recebido_raises_validation_error(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """respond() com status 'recebido' levanta ValidationError."""
        with pytest.raises(ValidationError):
            await whistleblower_service.respond(
                report_id=REPORT_ID,
                company_id=COMPANY_ID,
                resposta_institucional="Resposta institucional aqui",
                status=WhistleblowerStatus.RECEBIDO,  # Status inválido para resposta
                respondido_por=USER_ID,
            )

        mock_whistleblower_repo.update_resposta.assert_not_called()

    async def test_respond_concluido_is_valid(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """respond() com status 'concluido' é válido."""
        updated_report = _make_fake_report(
            report_id=REPORT_ID,
            status="concluido",
        )
        mock_whistleblower_repo.update_resposta.return_value = updated_report

        result = await whistleblower_service.respond(
            report_id=REPORT_ID,
            company_id=COMPANY_ID,
            resposta_institucional="Caso concluído com as devidas providências.",
            status=WhistleblowerStatus.CONCLUIDO,
            respondido_por=USER_ID,
        )

        assert result.status == "concluido"

    async def test_respond_report_not_found_raises_not_found(
        self, whistleblower_service, mock_whistleblower_repo
    ):
        """respond() com relato inexistente levanta NotFoundError."""
        mock_whistleblower_repo.update_resposta.return_value = None

        with pytest.raises(NotFoundError):
            await whistleblower_service.respond(
                report_id=REPORT_ID,
                company_id=COMPANY_ID,
                resposta_institucional="Resposta institucional detalhada",
                status=WhistleblowerStatus.EM_ANALISE,
                respondido_por=USER_ID,
            )
