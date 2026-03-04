from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.user_role import UserRole
from src.infrastructure.database.session import get_db
from src.shared.exceptions import UnauthorizedError
from src.shared.security import decode_access_token

_bearer_scheme: HTTPBearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Dados do usuário autenticado extraídos e validados do JWT."""

    user_id: UUID
    company_id: UUID
    role: UserRole


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Dependência FastAPI que valida o JWT e configura o contexto RLS na sessão do banco.

    Decodifica o access token, extrai os claims e executa SET LOCAL app.company_id
    na sessão PostgreSQL atual para ativar as políticas de Row Level Security.
    """
    if not credentials:
        raise UnauthorizedError("Token de acesso não fornecido")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc

    user_id_raw: str | None = payload.get("sub")
    company_id_raw: str | None = payload.get("company_id")
    role_raw: str | None = payload.get("role")

    if not user_id_raw or not company_id_raw or not role_raw:
        raise UnauthorizedError("Token inválido — claims obrigatórios ausentes")

    try:
        user_id = UUID(user_id_raw)
        company_id = UUID(company_id_raw)
        role = UserRole(role_raw)
    except (ValueError, KeyError) as exc:
        raise UnauthorizedError("Token inválido — formato de claims incorreto") from exc

    # Configura company_id e user_id na sessão PostgreSQL para ativar as políticas de RLS.
    # SET LOCAL garante que a configuração vale apenas para a transação atual.
    # app.company_id: isolamento multi-tenant (campanhas, planos, etc.)
    # app.user_id: isolamento por usuário (notificações in-app — Módulo 08)
    await db.execute(
        text("SET LOCAL app.company_id = :company_id"),
        {"company_id": str(company_id)},
    )
    await db.execute(
        text("SET LOCAL app.user_id = :user_id"),
        {"user_id": str(user_id)},
    )

    return CurrentUser(user_id=user_id, company_id=company_id, role=role)
