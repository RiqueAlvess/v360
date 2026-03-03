from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.auth_service import AuthService
from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.models.task_queue import TaskQueue
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.token_repository import SQLTokenRepository
from src.infrastructure.repositories.user_repository import SQLUserRepository
from src.presentation.schemas.auth_schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)

router: APIRouter = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_service(db: AsyncSession) -> AuthService:
    """Constrói AuthService com suas dependências concretas."""
    return AuthService(
        user_repo=SQLUserRepository(db),
        token_repo=SQLTokenRepository(db),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuário",
    description="Autentica com email e senha — retorna access token (15 min) e refresh token (30 dias).",
)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    service = _build_auth_service(db)
    tokens = await service.login(body.email, body.password)
    await db.commit()
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Renovar tokens",
    description="Rotaciona o refresh token — invalida o atual e emite novo par de tokens.",
)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    service = _build_auth_service(db)
    tokens = await service.refresh(body.refresh_token)
    await db.commit()
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Encerrar sessão",
    description="Revoga o refresh token — access token expira naturalmente pelo TTL.",
)
async def logout(
    body: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = _build_auth_service(db)
    await service.logout(body.refresh_token)
    await db.commit()


@router.post(
    "/admin/schedule-token-cleanup",
    status_code=status.HTTP_201_CREATED,
    summary="Agendar limpeza de tokens expirados",
    description=(
        "Cria uma task na fila para limpar refresh tokens expirados. "
        "Destinado a ser chamado por um scheduler diário (cron)."
    ),
    include_in_schema=True,
)
async def schedule_token_cleanup(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Enfileira tarefa de limpeza de refresh tokens expirados na task_queue.

    O worker assíncrono (Blueprint 05) consumirá essa task e chamará
    TokenRepository.cleanup_expired() para remover os registros expirados.
    """
    task = TaskQueue(
        tipo=TaskQueueType.CLEANUP_EXPIRED_TOKENS,
        payload={"scheduled_at": datetime.now(tz=timezone.utc).isoformat()},
    )
    db.add(task)
    await db.commit()
    return {"mensagem": "Tarefa de limpeza agendada com sucesso"}
