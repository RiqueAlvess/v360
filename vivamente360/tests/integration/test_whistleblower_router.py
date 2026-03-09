"""Testes de integração do whistleblower_router — Blueprint 12.

ROTAS PÚBLICAS (sem autenticação):
    - POST /api/v1/denuncia/{slug}/submit   — submete relato anônimo
    - GET  /api/v1/denuncia/{slug}/consulta — consulta por token

ROTAS ADMIN (requerem JWT):
    - GET  /api/v1/admin/whistleblower/       — lista relatos com paginação
    - GET  /api/v1/admin/whistleblower/{id}   — detalhe de relato
    - PATCH /api/v1/admin/whistleblower/{id}/responder — registra resposta

ANONIMATO:
    - Rotas públicas não requerem JWT
    - Rotas admin exigem JWT com role ADMIN ou MANAGER
    - Nenhuma resposta expõe token_hash
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
REPORT_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
COMPANY_SLUG = "empresa-abc"


def _make_fake_report(status: str = "recebido", anonimo: bool = True):
    report = MagicMock()
    report.id = REPORT_ID
    report.company_id = COMPANY_ID
    # token_hash NUNCA deve ser exposto
    report.token_hash = "a" * 64
    report.categoria = "assedio_moral"
    report.descricao = "Relato anônimo detalhado com mais de 20 chars"
    report.anonimo = anonimo
    report.nome_opcional = None if anonimo else "João"
    report.status = status
    report.resposta_institucional = None
    report.respondido_por = None
    report.respondido_em = None
    report.created_at = datetime.now(tz=timezone.utc)
    return report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def public_client(mock_session):
    """Client sem autenticação para testar rotas públicas."""
    from httpx import ASGITransport, AsyncClient
    from src.infrastructure.database.session import get_db
    from src.main import app

    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_wb_client(fake_current_user, mock_session):
    """Client autenticado para testar rotas admin."""
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
# POST /api/v1/denuncia/{slug}/submit — Rota PÚBLICA
# ---------------------------------------------------------------------------


class TestSubmitReport:
    async def test_submit_report_returns_201_with_token(self, public_client):
        """POST /denuncia/{slug}/submit retorna 201 com report_token."""
        fake_report = _make_fake_report()

        with (
            patch(
                "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.get_company_id_by_slug",
                new=AsyncMock(return_value=COMPANY_ID),
            ),
            patch(
                "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.create",
                new=AsyncMock(return_value=fake_report),
            ),
            patch(
                "src.infrastructure.queue.task_service.TaskService.enqueue",
                new=AsyncMock(),
            ),
            patch(
                "sqlalchemy.ext.asyncio.AsyncSession.execute",
                new=AsyncMock(),
            ),
        ):
            # Simplificamos: mockando o service diretamente
            pass

        # Usando patch no nível do service para simplificar
        with patch(
            "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
            new=AsyncMock(return_value=COMPANY_ID),
        ), patch(
            "src.application.services.whistleblower_service.WhistleblowerService.submit",
            new=AsyncMock(return_value={"report_token": "token_fake_aqui_com_43chars_xxxxxxxxxxx"}),
        ):
            response = await public_client.post(
                f"/api/v1/denuncia/{COMPANY_SLUG}/submit",
                json={
                    "categoria": "assedio_moral",
                    "descricao": "Relato detalhado sobre assédio moral no ambiente de trabalho",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert "report_token" in data
        # Jamais deve expor token_hash
        assert "token_hash" not in data

    async def test_submit_report_does_not_require_jwt(self, mock_session):
        """POST /denuncia/{slug}/submit funciona sem autenticação."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            with patch(
                "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
                new=AsyncMock(return_value=COMPANY_ID),
            ), patch(
                "src.application.services.whistleblower_service.WhistleblowerService.submit",
                new=AsyncMock(return_value={"report_token": "token_aqui_43chars_xxxxxxxx"}),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    response = await client.post(
                        f"/api/v1/denuncia/{COMPANY_SLUG}/submit",
                        json={
                            "categoria": "assedio_moral",
                            "descricao": "Relato detalhado com mais de 20 caracteres aqui",
                        },
                    )

            # Não deve retornar 401 (rota pública)
            assert response.status_code != 401
        finally:
            app.dependency_overrides.clear()

    async def test_submit_report_missing_fields_returns_422(self, public_client):
        """POST /denuncia/{slug}/submit sem campos obrigatórios retorna 422."""
        response = await public_client.post(
            f"/api/v1/denuncia/{COMPANY_SLUG}/submit",
            json={"categoria": "assedio_moral"},  # Sem descricao
        )

        assert response.status_code == 422

    async def test_submit_report_invalid_slug_returns_404(self, public_client):
        """POST /denuncia/{slug}/submit com slug inválido retorna 404."""
        with patch(
            "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
            side_effect=Exception("NotFound"),  # Simula NotFoundError
        ):
            pass

        from src.shared.exceptions import NotFoundError

        with patch(
            "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
            side_effect=NotFoundError("Canal de denúncias", "slug-invalido"),
        ):
            response = await public_client.post(
                "/api/v1/denuncia/slug-invalido/submit",
                json={
                    "categoria": "assedio_moral",
                    "descricao": "Relato detalhado com mais de 20 caracteres",
                },
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/denuncia/{slug}/consulta — Rota PÚBLICA
# ---------------------------------------------------------------------------


class TestConsultaReport:
    async def test_consulta_valid_token_returns_200(self, public_client):
        """GET /denuncia/{slug}/consulta retorna 200 com status."""
        with (
            patch(
                "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
                new=AsyncMock(return_value=COMPANY_ID),
            ),
            patch(
                "src.application.services.whistleblower_service.WhistleblowerService.consulta",
                new=AsyncMock(
                    return_value={
                        "status": "em_analise",
                        "resposta_institucional": None,
                        "respondido_em": None,
                    }
                ),
            ),
        ):
            response = await public_client.get(
                f"/api/v1/denuncia/{COMPANY_SLUG}/consulta",
                params={"token": "token_valido_com_exatos_43chars_xxxxxxxxxxx"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Nunca expõe dados identificáveis
        assert "token_hash" not in data
        assert "company_id" not in data

    async def test_consulta_does_not_require_jwt(self, mock_session):
        """GET /denuncia/{slug}/consulta funciona sem JWT."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            with (
                patch(
                    "src.application.services.whistleblower_service.WhistleblowerService.resolve_company_slug",
                    new=AsyncMock(return_value=COMPANY_ID),
                ),
                patch(
                    "src.application.services.whistleblower_service.WhistleblowerService.consulta",
                    new=AsyncMock(
                        return_value={
                            "status": "recebido",
                            "resposta_institucional": None,
                            "respondido_em": None,
                        }
                    ),
                ),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://testserver",
                ) as client:
                    response = await client.get(
                        f"/api/v1/denuncia/{COMPANY_SLUG}/consulta",
                        params={"token": "token_valido_com_exatos_43chars_xxxxxxxxxxx"},
                    )

            # Não deve retornar 401
            assert response.status_code != 401
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/admin/whistleblower/ — Rota ADMIN (autenticada)
# ---------------------------------------------------------------------------


class TestAdminListReports:
    async def test_list_reports_returns_200_with_pagination(self, admin_wb_client):
        """GET /admin/whistleblower/ retorna 200 com items e pagination."""
        fake_reports = [_make_fake_report()]

        with patch(
            "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.list_by_company",
            new=AsyncMock(return_value=(fake_reports, 1)),
        ):
            response = await admin_wb_client.get("/api/v1/admin/whistleblower/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data

    async def test_list_reports_does_not_expose_token_hash(self, admin_wb_client):
        """GET /admin/whistleblower/ não expõe token_hash nos items."""
        fake_reports = [_make_fake_report()]

        with patch(
            "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.list_by_company",
            new=AsyncMock(return_value=(fake_reports, 1)),
        ):
            response = await admin_wb_client.get("/api/v1/admin/whistleblower/")

        data = response.json()
        for item in data.get("items", []):
            assert "token_hash" not in item

    async def test_list_reports_requires_authentication(self, mock_session):
        """GET /admin/whistleblower/ sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/api/v1/admin/whistleblower/")
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_list_reports_with_status_filter(self, admin_wb_client):
        """GET /admin/whistleblower/?status=em_analise filtra por status."""
        with patch(
            "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.list_by_company",
            new=AsyncMock(return_value=([], 0)),
        ):
            response = await admin_wb_client.get(
                "/api/v1/admin/whistleblower/?status=em_analise"
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/admin/whistleblower/{id} — Rota ADMIN
# ---------------------------------------------------------------------------


class TestAdminGetReport:
    async def test_get_report_returns_200(self, admin_wb_client):
        """GET /admin/whistleblower/{id} retorna 200 com dados do relato."""
        fake_report = _make_fake_report()

        with patch(
            "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.get_by_id",
            new=AsyncMock(return_value=fake_report),
        ):
            response = await admin_wb_client.get(
                f"/api/v1/admin/whistleblower/{REPORT_ID}"
            )

        assert response.status_code == 200
        data = response.json()
        # token_hash nunca exposto
        assert "token_hash" not in data

    async def test_get_report_not_found_returns_404(self, admin_wb_client):
        """GET /admin/whistleblower/{id} com ID inexistente retorna 404."""
        with patch(
            "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ):
            response = await admin_wb_client.get(
                f"/api/v1/admin/whistleblower/{uuid.uuid4()}"
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/whistleblower/{id}/responder — Rota ADMIN
# ---------------------------------------------------------------------------


class TestAdminRespondToReport:
    async def test_respond_returns_200(self, admin_wb_client):
        """PATCH /admin/whistleblower/{id}/responder retorna 200."""
        updated_report = _make_fake_report(status="em_analise")
        updated_report.resposta_institucional = "Estamos investigando."
        updated_report.respondido_por = USER_ID
        updated_report.respondido_em = datetime.now(tz=timezone.utc)

        with (
            patch(
                "src.infrastructure.repositories.whistleblower_repository.SQLWhistleblowerRepository.update_resposta",
                new=AsyncMock(return_value=updated_report),
            ),
        ):
            response = await admin_wb_client.patch(
                f"/api/v1/admin/whistleblower/{REPORT_ID}/responder",
                json={
                    "resposta_institucional": "Estamos investigando o ocorrido com cuidado.",
                    "status": "em_analise",
                },
            )

        assert response.status_code == 200

    async def test_respond_invalid_status_returns_422(self, admin_wb_client):
        """PATCH /responder com status inválido retorna 422."""
        response = await admin_wb_client.patch(
            f"/api/v1/admin/whistleblower/{REPORT_ID}/responder",
            json={
                "resposta_institucional": "Resposta aqui com mais de 10 chars",
                "status": "status_invalido",
            },
        )

        assert response.status_code == 422

    async def test_respond_requires_authentication(self, mock_session):
        """PATCH /responder sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.patch(
                    f"/api/v1/admin/whistleblower/{REPORT_ID}/responder",
                    json={
                        "resposta_institucional": "Resposta institucional aqui.",
                        "status": "em_analise",
                    },
                )
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()
