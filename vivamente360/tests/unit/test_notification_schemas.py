"""Testes unitários dos Schemas de Notificações — Blueprint 10.

Cobre:
    - NotificationResponse: serialização com from_attributes
    - NotificationListResponse: estrutura paginada com total_nao_lidas
    - NotificationCountResponse: badge count
    - NotificationReadResponse: updated count
    - NotificationDeleteResponse: deleted count
    - PaginationMeta: estrutura de paginação
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestNotificationResponse:
    def test_notification_response_valid(self):
        """NotificationResponse é criado com todos os campos obrigatórios."""
        from src.domain.enums.notification_tipo import NotificationTipo
        from src.presentation.schemas.notification_schemas import NotificationResponse

        notif = NotificationResponse(
            id=uuid.uuid4(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            tipo=NotificationTipo.CAMPANHA_ENCERRADA,
            titulo="Campanha encerrada",
            mensagem="A campanha foi encerrada.",
            lida=False,
            deletada=False,
            created_at=datetime.now(tz=timezone.utc),
            metadata_={},
        )

        assert notif.lida is False
        assert notif.deletada is False

    def test_notification_response_with_optional_fields(self):
        """NotificationResponse com campos opcionais (link, lida_em) é válido."""
        from src.domain.enums.notification_tipo import NotificationTipo
        from src.presentation.schemas.notification_schemas import NotificationResponse

        now = datetime.now(tz=timezone.utc)
        notif = NotificationResponse(
            id=uuid.uuid4(),
            company_id=COMPANY_ID,
            user_id=USER_ID,
            tipo=NotificationTipo.RELATORIO_PRONTO,
            titulo="Relatório pronto",
            mensagem="Seu relatório está disponível.",
            link="/reports/123",
            lida=True,
            lida_em=now,
            deletada=False,
            created_at=now,
            metadata_={},
        )

        assert notif.link == "/reports/123"
        assert notif.lida_em == now

    def test_notification_response_missing_required_fields_raises_error(self):
        """Campos obrigatórios ausentes levantam ValidationError."""
        from src.presentation.schemas.notification_schemas import NotificationResponse

        with pytest.raises(ValidationError):
            NotificationResponse()


class TestNotificationListResponse:
    def test_notification_list_response_structure(self):
        """NotificationListResponse contém items, total_nao_lidas e pagination."""
        from src.presentation.schemas.notification_schemas import (
            NotificationListResponse,
            PaginationMeta,
        )

        response = NotificationListResponse(
            items=[],
            total_nao_lidas=3,
            pagination=PaginationMeta(page=1, page_size=20, total=0, pages=0),
        )

        assert response.items == []
        assert response.total_nao_lidas == 3
        assert response.pagination.page == 1

    def test_notification_list_response_requires_all_fields(self):
        """Ausência de campos obrigatórios levanta ValidationError."""
        from src.presentation.schemas.notification_schemas import NotificationListResponse

        with pytest.raises(ValidationError):
            NotificationListResponse(items=[])


class TestNotificationCountResponse:
    def test_count_response_valid(self):
        """NotificationCountResponse com nao_lidas inteiro é válido."""
        from src.presentation.schemas.notification_schemas import NotificationCountResponse

        response = NotificationCountResponse(nao_lidas=5)
        assert response.nao_lidas == 5

    def test_count_response_zero(self):
        """NotificationCountResponse com nao_lidas=0 é válido."""
        from src.presentation.schemas.notification_schemas import NotificationCountResponse

        response = NotificationCountResponse(nao_lidas=0)
        assert response.nao_lidas == 0


class TestNotificationReadResponse:
    def test_read_response_valid(self):
        """NotificationReadResponse com updated inteiro é válido."""
        from src.presentation.schemas.notification_schemas import NotificationReadResponse

        response = NotificationReadResponse(updated=3)
        assert response.updated == 3


class TestNotificationDeleteResponse:
    def test_delete_response_valid(self):
        """NotificationDeleteResponse com deleted inteiro é válido."""
        from src.presentation.schemas.notification_schemas import NotificationDeleteResponse

        response = NotificationDeleteResponse(deleted=1)
        assert response.deleted == 1


class TestPaginationMeta:
    def test_pagination_meta_valid(self):
        """PaginationMeta com todos os campos é válida."""
        from src.presentation.schemas.notification_schemas import PaginationMeta

        pagination = PaginationMeta(page=2, page_size=20, total=45, pages=3)
        assert pagination.page == 2
        assert pagination.pages == 3
