"""Modelo ORM para o sistema de notificações in-app — Módulo 08.

Regra R1: type hints completos em todos os campos.
Regra R5: RLS habilitada — isolamento por user_id via SET LOCAL app.user_id.
Soft delete: campo deletada=True + deletada_em — nunca hard delete (Regra do Módulo 08).
"""
import uuid
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums.notification_tipo import NotificationTipo
from src.infrastructure.database.models.base import Base


class Notification(Base):
    """Notificação in-app para um usuário da plataforma.

    Gerada por eventos do sistema: campanha encerrada, relatório pronto,
    nova denúncia, plano vencendo, análise de IA concluída, etc.
    Soft delete — usuário 'apaga' sem perder histórico de auditoria.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[NotificationTipo] = mapped_column(
        sa.Enum(NotificationTipo, name="notification_tipo", create_type=False),
        nullable=False,
    )
    titulo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    mensagem: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Rota frontend para navegar ao item relacionado
    link: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    lida: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    lida_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Soft delete — preserva histórico para auditoria
    deletada: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    deletada_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    # Dados extras estruturados (campaign_id, plan_id, etc.)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="'{}'",
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Índice parcial para performance do badge de não lidas
        sa.Index(
            "idx_notifications_user_unread",
            "user_id",
            "lida",
            postgresql_where=sa.text("lida = FALSE AND deletada = FALSE"),
        ),
        # Índice composto para listagem paginada por usuário
        sa.Index(
            "idx_notifications_user_created",
            "user_id",
            "created_at",
        ),
    )
