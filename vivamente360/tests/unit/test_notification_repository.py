"""Testes unitários do SQLNotificationRepository — Blueprint 10.

Cobre:
    - create(): persiste notificação com flush
    - list_by_user(): paginação, filtro lida, badge count
    - count_unread(): retorna inteiro correto
    - mark_read(): seta lida=True, preserva deletada=False
    - mark_all_read(): atualiza em batch, retorna rowcount
    - soft_delete(): seta deletada=True, nunca hard delete
    - soft_delete_all_read(): soft delete em batch das lidas
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.enums.notification_tipo import NotificationTipo


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
NOTIF_ID = uuid.uuid4()


def _make_fake_notification(
    notif_id: uuid.UUID = None,
    user_id: uuid.UUID = USER_ID,
    lida: bool = False,
    deletada: bool = False,
):
    notif = MagicMock()
    notif.id = notif_id or uuid.uuid4()
    notif.company_id = COMPANY_ID
    notif.user_id = user_id
    notif.tipo = NotificationTipo.CAMPANHA_ENCERRADA
    notif.titulo = "Campanha encerrada"
    notif.mensagem = "A campanha foi encerrada com sucesso."
    notif.link = "/campaigns/123"
    notif.lida = lida
    notif.lida_em = datetime.now(tz=timezone.utc) if lida else None
    notif.deletada = deletada
    notif.deletada_em = datetime.now(tz=timezone.utc) if deletada else None
    notif.metadata_ = {}
    notif.created_at = datetime.now(tz=timezone.utc)
    return notif


class TestSQLNotificationRepositoryCreate:
    async def test_create_adds_and_flushes(self, mock_session):
        """create() adiciona notificação à sessão e faz flush."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        repo = SQLNotificationRepository(mock_session)
        result = await repo.create(
            company_id=COMPANY_ID,
            user_id=USER_ID,
            tipo=NotificationTipo.CAMPANHA_ENCERRADA,
            titulo="Campanha encerrada",
            mensagem="A campanha foi encerrada.",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_create_with_optional_fields(self, mock_session):
        """create() com link e metadata é aceito."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        repo = SQLNotificationRepository(mock_session)
        result = await repo.create(
            company_id=COMPANY_ID,
            user_id=USER_ID,
            tipo=NotificationTipo.RELATORIO_PRONTO,
            titulo="Relatório pronto",
            mensagem="Seu relatório está disponível.",
            link="/reports/123",
            metadata={"report_id": "123"},
        )

        mock_session.add.assert_called_once()


class TestSQLNotificationRepositoryListByUser:
    async def test_list_by_user_returns_tuple_with_three_values(self, mock_session):
        """list_by_user retorna (items, total_filtrado, total_nao_lidas)."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        fake_items = [_make_fake_notification() for _ in range(3)]

        # Execute é chamado 3 vezes: count_stmt, badge_stmt, items_stmt
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        badge_result = MagicMock()
        badge_result.scalar_one.return_value = 2

        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = fake_items
        items_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(
            side_effect=[count_result, badge_result, items_result]
        )

        repo = SQLNotificationRepository(mock_session)
        items, total, nao_lidas = await repo.list_by_user(user_id=USER_ID)

        assert total == 3
        assert nao_lidas == 2
        assert len(items) == 3

    async def test_list_by_user_with_lida_filter(self, mock_session):
        """list_by_user com lida=True filtra apenas lidas."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        badge_result = MagicMock()
        badge_result.scalar_one.return_value = 0
        items_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        items_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(
            side_effect=[count_result, badge_result, items_result]
        )

        repo = SQLNotificationRepository(mock_session)
        items, total, nao_lidas = await repo.list_by_user(
            user_id=USER_ID, lida=True
        )

        assert total == 0


class TestSQLNotificationRepositoryCountUnread:
    async def test_count_unread_returns_integer(self, mock_session):
        """count_unread retorna inteiro correto."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.scalar_one.return_value = 5
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLNotificationRepository(mock_session)
        count = await repo.count_unread(USER_ID)

        assert count == 5


class TestSQLNotificationRepositoryMarkRead:
    async def test_mark_read_returns_notification_when_found(self, mock_session):
        """mark_read retorna notificação atualizada quando encontrada."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        fake_notif = _make_fake_notification(lida=True)
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_notif
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        notif = await repo.mark_read(
            notification_id=NOTIF_ID, user_id=USER_ID
        )

        assert notif.lida is True
        mock_session.flush.assert_called_once()

    async def test_mark_read_returns_none_when_not_found(self, mock_session):
        """mark_read retorna None quando notificação não encontrada."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result)

        repo = SQLNotificationRepository(mock_session)
        notif = await repo.mark_read(notification_id=NOTIF_ID, user_id=USER_ID)

        assert notif is None

    async def test_mark_read_preserves_deletada_false(self, mock_session):
        """mark_read não altera campo deletada — permanece False."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        fake_notif = _make_fake_notification(lida=False, deletada=False)
        result = MagicMock()
        result.scalar_one_or_none.return_value = fake_notif
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        await repo.mark_read(notification_id=NOTIF_ID, user_id=USER_ID)

        assert fake_notif.deletada is False


class TestSQLNotificationRepositoryMarkAllRead:
    async def test_mark_all_read_returns_rowcount(self, mock_session):
        """mark_all_read retorna número de notificações atualizadas."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.rowcount = 7
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        updated = await repo.mark_all_read(USER_ID)

        assert updated == 7
        mock_session.flush.assert_called_once()


class TestSQLNotificationRepositorySoftDelete:
    async def test_soft_delete_returns_true_when_found(self, mock_session):
        """soft_delete retorna True e seta deletada=True quando notificação existe."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        deleted = await repo.soft_delete(
            notification_id=NOTIF_ID, user_id=USER_ID
        )

        assert deleted is True
        mock_session.flush.assert_called_once()

    async def test_soft_delete_returns_false_when_not_found(self, mock_session):
        """soft_delete retorna False quando notificação não existe."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        deleted = await repo.soft_delete(
            notification_id=NOTIF_ID, user_id=USER_ID
        )

        assert deleted is False

    async def test_soft_delete_never_hard_deletes(self, mock_session):
        """soft_delete usa UPDATE, nunca DELETE — verifica que session.delete não é chamado."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        await repo.soft_delete(notification_id=NOTIF_ID, user_id=USER_ID)

        # delete() jamais deve ser chamado diretamente
        assert not hasattr(mock_session, "delete") or not mock_session.delete.called


class TestSQLNotificationRepositorySoftDeleteAllRead:
    async def test_soft_delete_all_read_returns_count(self, mock_session):
        """soft_delete_all_read retorna número de notificações deletadas."""
        from src.infrastructure.repositories.notification_repository import (
            SQLNotificationRepository,
        )

        result = MagicMock()
        result.rowcount = 4
        mock_session.execute = AsyncMock(return_value=result)
        mock_session.flush = AsyncMock()

        repo = SQLNotificationRepository(mock_session)
        deleted = await repo.soft_delete_all_read(USER_ID)

        assert deleted == 4
