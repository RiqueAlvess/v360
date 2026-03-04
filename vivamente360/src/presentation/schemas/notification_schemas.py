"""Schemas Pydantic para o módulo de Notificações In-App — Módulo 08.

Regra R1: type hints completos em todos os campos.
Regra R4: respostas de listagem sempre incluem PaginationMeta.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums.notification_tipo import NotificationTipo


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    """Representa uma notificação in-app na resposta da API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    user_id: UUID
    tipo: NotificationTipo
    titulo: str
    mensagem: str
    link: Optional[str] = None
    lida: bool
    lida_em: Optional[datetime] = None
    deletada: bool
    deletada_em: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PaginationMeta(BaseModel):
    """Metadados de paginação incluídos em todas as listagens — Regra R4."""

    page: int = Field(..., description="Página atual (1-indexed).")
    page_size: int = Field(..., description="Itens por página.")
    total: int = Field(..., description="Total de itens respeitando filtros.")
    pages: int = Field(..., description="Total de páginas.")


class NotificationListResponse(BaseModel):
    """Resposta paginada do endpoint GET /notifications."""

    items: list[NotificationResponse]
    total_nao_lidas: int = Field(
        ...,
        description="Badge count: total de notificações não lidas (sem filtros de lida).",
    )
    pagination: PaginationMeta


class NotificationCountResponse(BaseModel):
    """Resposta do endpoint GET /notifications/count — para polling do badge."""

    nao_lidas: int = Field(..., description="Total de notificações não lidas.")


class NotificationReadResponse(BaseModel):
    """Resposta após marcar uma ou todas as notificações como lidas."""

    updated: int = Field(..., description="Número de notificações atualizadas.")


class NotificationDeleteResponse(BaseModel):
    """Resposta após deletar uma ou todas as notificações lidas."""

    deleted: int = Field(..., description="Número de notificações deletadas.")
