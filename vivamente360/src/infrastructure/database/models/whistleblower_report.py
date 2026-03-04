"""Modelo ORM do Canal de Denúncias Anônimo — Módulo 07.

ANONIMATO GARANTIDO:
    - token_hash: SHA-256 do token entregue ao denunciante (token raw NUNCA persiste).
    - Nenhum IP, cookie ou dado de sessão é armazenado.
    - nome_opcional é preenchido APENAS se o denunciante optar explicitamente
      por se identificar (anonimo=False).
    - Moderadores veem o relato mas não têm como identificar o denunciante.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.whistleblower_categoria import WhistleblowerCategoria
from src.domain.enums.whistleblower_status import WhistleblowerStatus
from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.user import User


class WhistleblowerReport(Base):
    """Relato anônimo do canal de denúncias (NR-1 / Portaria MTE 1.419/2024).

    RLS ativa — política rls_whistleblower_reports filtra por company_id.
    Apenas admins e compliance da empresa podem listar ou responder relatos.
    O denunciante acessa apenas via report_token (exibido uma única vez).
    """

    __tablename__ = "whistleblower_reports"

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
    # SHA-256 hex digest do token entregue ao denunciante.
    # O token raw (secrets.token_urlsafe(32)) é exibido APENAS UMA VEZ ao denunciante.
    token_hash: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
    )
    categoria: Mapped[WhistleblowerCategoria] = mapped_column(
        sa.String(50),
        nullable=False,
    )
    descricao: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    # Padrão: relato anônimo. Denunciante pode optar por se identificar.
    anonimo: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=True,
        server_default=sa.text("TRUE"),
    )
    # Preenchido SOMENTE quando anonimo=False — decisão exclusiva do denunciante.
    nome_opcional: Mapped[Optional[str]] = mapped_column(sa.Text(), nullable=True)
    status: Mapped[WhistleblowerStatus] = mapped_column(
        sa.String(20),
        nullable=False,
        default=WhistleblowerStatus.RECEBIDO,
        server_default=sa.text("'recebido'"),
    )
    resposta_institucional: Mapped[Optional[str]] = mapped_column(
        sa.Text(), nullable=True
    )
    respondido_por: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    respondido_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.text("NOW()"),
        nullable=False,
    )

    # Relationship para o usuário que registrou a resposta institucional
    respondente: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[respondido_por],
        lazy="noload",
    )
