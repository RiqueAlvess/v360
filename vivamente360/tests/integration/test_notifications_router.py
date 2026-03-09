"""Testes de integração do notifications_router — Blueprint 10.

Cobre:
    - GET  /api/v1/notifications              — lista paginada com badge
    - GET  /api/v1/notifications/count        — badge count de não lidas
    - PATCH /api/v1/notifications/{id}/read   — marca como lida
    - PATCH /api/v1/notifications/read-all    — marca todas como lidas
    - DELETE /api/v1/notifications/{id}       — soft delete
    - DELETE /api/v1/notifications/clear-all  — soft delete de todas as lidas
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NOTIF_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def _make_fake_notification(lida: bool = False):
    from src.domain.enums.notification_tipo import NotificationTipo

    notif = MagicMock()
    notif.id = NOTIF_ID
    notif.company_id = COMPANY_ID
    notif.user_id = USER_ID
    notif.tipo = NotificationTipo.CAMPANHA_ENCERRADA
    notif.titulo = "Campanha encerrada"
    notif.mensagem = "A campanha foi encerrada com sucesso."
    notif.link = "/campaigns/123"
    notif.lida = lida
    notif.lida_em = datetime.now(tz=timezone.utc) if lida else None
    notif.deletada = False
    notif.deletada_em = None
    notif.metadata_ = {}
    notif.created_at = datetime.now(tz=timezone.utc)
    return notif


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def notif_client(fake_current_user, mock_session):
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
# GET /api/v1/notifications
# ---------------------------------------------------------------------------


class TestListNotifications:
    async def test_list_notifications_returns_200(self, notif_client):
        """GET /notifications retorna 200 com items e pagination."""
        fake_items = [_make_fake_notification()]

        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.list_by_user",
            new=AsyncMock(return_value=(fake_items, 1, 1)),
        ):
            response = await notif_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert "total_nao_lidas" in data

    async def test_list_notifications_empty_returns_200(self, notif_client):
        """GET /notifications sem notificações retorna 200 com lista vazia."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.list_by_user",
            new=AsyncMock(return_value=([], 0, 0)),
        ):
            response = await notif_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_nao_lidas"] == 0

    async def test_list_notifications_with_lida_filter(self, notif_client):
        """GET /notifications?lida=false filtra não lidas."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.list_by_user",
            new=AsyncMock(return_value=([], 0, 0)),
        ):
            response = await notif_client.get("/api/v1/notifications?lida=false")

        assert response.status_code == 200

    async def test_list_notifications_requires_authentication(self, mock_session):
        """GET /notifications sem JWT retorna 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get("/api/v1/notifications")
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/count
# ---------------------------------------------------------------------------


class TestCountUnreadNotifications:
    async def test_count_unread_returns_200(self, notif_client):
        """GET /notifications/count retorna 200 com badge count."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.count_unread",
            new=AsyncMock(return_value=5),
        ):
            response = await notif_client.get("/api/v1/notifications/count")

        assert response.status_code == 200
        data = response.json()
        assert data["nao_lidas"] == 5

    async def test_count_unread_zero(self, notif_client):
        """GET /notifications/count com zero não lidas retorna 0."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.count_unread",
            new=AsyncMock(return_value=0),
        ):
            response = await notif_client.get("/api/v1/notifications/count")

        assert response.status_code == 200
        assert response.json()["nao_lidas"] == 0


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/{id}/read
# ---------------------------------------------------------------------------


class TestMarkNotificationRead:
    async def test_mark_read_returns_200(self, notif_client):
        """PATCH /notifications/{id}/read retorna 200 com notificação atualizada."""
        fake_notif = _make_fake_notification(lida=True)

        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.mark_read",
            new=AsyncMock(return_value=fake_notif),
        ):
            response = await notif_client.patch(
                f"/api/v1/notifications/{NOTIF_ID}/read"
            )

        assert response.status_code == 200

    async def test_mark_read_not_found_returns_404(self, notif_client):
        """PATCH /notifications/{id}/read com ID inexistente retorna 404."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.mark_read",
            new=AsyncMock(return_value=None),
        ):
            response = await notif_client.patch(
                f"/api/v1/notifications/{uuid.uuid4()}/read"
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/notifications/read-all
# ---------------------------------------------------------------------------


class TestMarkAllNotificationsRead:
    async def test_mark_all_read_returns_200(self, notif_client):
        """PATCH /notifications/read-all retorna 200 com count de atualizadas."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.mark_all_read",
            new=AsyncMock(return_value=7),
        ):
            response = await notif_client.patch("/api/v1/notifications/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 7


# ---------------------------------------------------------------------------
# DELETE /api/v1/notifications/{id}
# ---------------------------------------------------------------------------


class TestDeleteNotification:
    async def test_delete_notification_returns_200(self, notif_client):
        """DELETE /notifications/{id} retorna 200 (soft delete bem-sucedido)."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.soft_delete",
            new=AsyncMock(return_value=True),
        ):
            response = await notif_client.delete(f"/api/v1/notifications/{NOTIF_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1

    async def test_delete_notification_not_found_returns_404(self, notif_client):
        """DELETE /notifications/{id} com ID inexistente retorna 404."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.soft_delete",
            new=AsyncMock(return_value=False),
        ):
            response = await notif_client.delete(
                f"/api/v1/notifications/{uuid.uuid4()}"
            )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/notifications/clear-all
# ---------------------------------------------------------------------------


class TestClearAllReadNotifications:
    async def test_clear_all_read_returns_200(self, notif_client):
        """DELETE /notifications/clear-all retorna 200 com count deletadas."""
        with patch(
            "src.infrastructure.repositories.notification_repository.SQLNotificationRepository.soft_delete_all_read",
            new=AsyncMock(return_value=4),
        ):
            response = await notif_client.delete("/api/v1/notifications/clear-all")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 4
