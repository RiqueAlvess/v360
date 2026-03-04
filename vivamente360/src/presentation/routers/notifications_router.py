"""Router do módulo de Notificações In-App — Módulo 08.

Regra R2: Controllers/Routers só validam entrada e delegam ao Service.
Regra R4: Endpoint de listagem tem paginação (page + page_size, máx. 100).
Regra R1: Type hints completos em todos os parâmetros.

Endpoints implementados:
    GET    /notifications                 — lista paginada com badge de não lidas
    GET    /notifications/count           — badge leve (polling 60s)
    PATCH  /notifications/{id}/read       — marca uma notificação como lida
    PATCH  /notifications/read-all        — marca todas como lidas
    DELETE /notifications/{id}            — soft delete de uma notificação
    DELETE /notifications/clear-all       — soft delete de todas as lidas
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.notification_service import NotificationService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.notification_repository import (
    SQLNotificationRepository,
)
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.notification_schemas import (
    NotificationCountResponse,
    NotificationDeleteResponse,
    NotificationListResponse,
    NotificationReadResponse,
    NotificationResponse,
)

router: APIRouter = APIRouter(prefix="/notifications", tags=["notifications"])

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


def _build_service(db: AsyncSession) -> NotificationService:
    """Constrói o NotificationService com as dependências corretas para a requisição."""
    return NotificationService(
        notification_repo=SQLNotificationRepository(db),
        db=db,
    )


# ---------------------------------------------------------------------------
# GET /notifications/count  (deve vir antes de /{id} para evitar conflito)
# ---------------------------------------------------------------------------


@router.get(
    "/count",
    response_model=NotificationCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Conta notificações não lidas (badge)",
    description=(
        "Retorna o total de notificações não lidas do usuário autenticado. "
        "Endpoint leve projetado para polling a cada 60 segundos pelo frontend. "
        "Notificações deletadas não são contabilizadas."
    ),
)
async def count_unread_notifications(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationCountResponse:
    """Retorna o badge count de notificações não lidas."""
    service = _build_service(db)
    nao_lidas = await service.count_unread(current_user.user_id)
    return NotificationCountResponse(nao_lidas=nao_lidas)


# ---------------------------------------------------------------------------
# PATCH /notifications/read-all  (deve vir antes de /{id} para evitar conflito)
# ---------------------------------------------------------------------------


@router.patch(
    "/read-all",
    response_model=NotificationReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Marca todas as notificações como lidas",
    description=(
        "Marca todas as notificações não lidas do usuário autenticado como lidas "
        "em uma única operação SQL. Notificações já lidas ou deletadas são ignoradas."
    ),
)
async def mark_all_notifications_read(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationReadResponse:
    """Marca todas as notificações como lidas em uma única operação."""
    service = _build_service(db)
    updated = await service.mark_all_read(current_user.user_id)
    return NotificationReadResponse(updated=updated)


# ---------------------------------------------------------------------------
# DELETE /notifications/clear-all  (deve vir antes de /{id} para evitar conflito)
# ---------------------------------------------------------------------------


@router.delete(
    "/clear-all",
    response_model=NotificationDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Limpa todas as notificações lidas",
    description=(
        "Soft delete em todas as notificações já lidas do usuário autenticado. "
        "Notificações não lidas são preservadas. "
        "Os registros permanecem no banco com deletada=True para auditoria."
    ),
)
async def clear_all_read_notifications(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationDeleteResponse:
    """Soft delete em todas as notificações lidas do usuário."""
    service = _build_service(db)
    deleted = await service.clear_all_read(current_user.user_id)
    return NotificationDeleteResponse(deleted=deleted)


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista notificações do usuário",
    description=(
        "Retorna as notificações visíveis do usuário autenticado com paginação. "
        "Notificações deletadas nunca aparecem. "
        "O campo 'total_nao_lidas' é sempre o badge count total (sem filtro de lida). "
        "Use ?lida=false para ver apenas não lidas."
    ),
)
async def list_notifications(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    lida: Annotated[
        Optional[bool],
        Query(description="Filtrar por status de leitura (true=lidas, false=não lidas)."),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> NotificationListResponse:
    """Lista notificações paginadas com badge count de não lidas."""
    service = _build_service(db)
    result = await service.list_notifications(
        user_id=current_user.user_id,
        lida=lida,
        page=page,
        page_size=page_size,
    )

    from src.presentation.schemas.notification_schemas import PaginationMeta

    return NotificationListResponse(
        items=result["items"],
        total_nao_lidas=result["total_nao_lidas"],
        pagination=PaginationMeta(**result["pagination"]),
    )


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Marca uma notificação como lida",
    description=(
        "Marca a notificação especificada como lida e registra lida_em. "
        "Retorna 404 se a notificação não existir ou não pertencer ao usuário autenticado."
    ),
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationResponse:
    """Marca notificação como lida e retorna o objeto atualizado."""
    from src.shared.exceptions import NotFoundError

    service = _build_service(db)
    notification = await service.mark_read(
        notification_id=notification_id,
        user_id=current_user.user_id,
    )

    if notification is None:
        raise NotFoundError("Notification", notification_id)

    return NotificationResponse.model_validate(notification)


# ---------------------------------------------------------------------------
# DELETE /notifications/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{notification_id}",
    response_model=NotificationDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft delete de uma notificação",
    description=(
        "Remove a notificação da listagem do usuário (deletada=True + deletada_em=NOW()). "
        "O registro permanece no banco para auditoria — nunca é hard deleted. "
        "Retorna 404 se a notificação não existir ou não pertencer ao usuário autenticado."
    ),
)
async def delete_notification(
    notification_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NotificationDeleteResponse:
    """Soft delete da notificação especificada."""
    from src.shared.exceptions import NotFoundError

    service = _build_service(db)
    deleted = await service.delete_notification(
        notification_id=notification_id,
        user_id=current_user.user_id,
    )

    if not deleted:
        raise NotFoundError("Notification", notification_id)

    return NotificationDeleteResponse(deleted=1)
