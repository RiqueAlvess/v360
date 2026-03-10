"""Modelo ORM para o módulo de Plano de Ação.

Regra R1: type hints completos em todos os campos e relacionamentos.
Regra R5: RLS habilitada — isolamento multi-tenant por company_id.
"""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.organizational_unit import OrganizationalUnit
    from src.infrastructure.database.models.sector import Sector
    from src.infrastructure.database.models.user import User


class ActionPlan(Base, TimestampMixin):
    """Plano de Ação vinculado a uma campanha de avaliação psicossocial.

    Fecha o ciclo diagnóstico: diagnóstico → plano → execução → evidência.
    Soft delete via status='cancelado' — sem hard delete.
    """

    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(sa.Text, nullable=False)
    descricao: Mapped[str] = mapped_column(sa.Text, nullable=False)
    dimensao: Mapped[Optional[str]] = mapped_column(
        sa.String(50), nullable=True
    )
    unidade_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    setor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
    )
    responsavel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    responsavel_externo: Mapped[Optional[str]] = mapped_column(
        sa.String(200), nullable=True
    )
    nivel_risco: Mapped[NivelRisco] = mapped_column(
        sa.Enum(NivelRisco, name="nivel_risco", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    status: Mapped[ActionPlanStatus] = mapped_column(
        sa.Enum(ActionPlanStatus, name="action_plan_status", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ActionPlanStatus.PENDENTE,
    )
    prazo: Mapped[date] = mapped_column(sa.Date, nullable=False)
    concluido_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", foreign_keys=[campaign_id])
    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
    unidade: Mapped[Optional["OrganizationalUnit"]] = relationship(
        "OrganizationalUnit", foreign_keys=[unidade_id]
    )
    setor: Mapped[Optional["Sector"]] = relationship(
        "Sector", foreign_keys=[setor_id]
    )
    responsavel: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[responsavel_id]
    )
    criador: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by]
    )
