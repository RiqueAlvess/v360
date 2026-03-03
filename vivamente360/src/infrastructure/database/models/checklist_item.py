import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign
    from src.infrastructure.database.models.checklist_template import ChecklistTemplate
    from src.infrastructure.database.models.user import User


class ChecklistItem(Base):
    """Item de conformidade NR-1 vinculado a uma campanha específica.

    Criado automaticamente pelo CampaignService a partir dos ChecklistTemplates
    quando uma nova campanha é criada. Suporta toggle de conclusão, observações
    e evidências (file_assets com contexto='checklist_evidencia').

    A tabela tem RLS ativa — o isolamento multi-tenant é garantido pelo banco
    via company_id = current_setting('app.company_id')::uuid.
    """

    __tablename__ = "checklist_items"
    __table_args__ = (
        sa.UniqueConstraint(
            "campaign_id",
            "template_id",
            name="uq_checklist_items_campaign_template",
        ),
    )

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
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("checklist_templates.id"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )
    concluido: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    concluido_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    concluido_por: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    observacao: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    prazo: Mapped[Optional[date]] = mapped_column(sa.Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationships
    template: Mapped["ChecklistTemplate"] = relationship(
        "ChecklistTemplate",
        lazy="joined",
    )
    campaign: Mapped["Campaign"] = relationship("Campaign")
    concluido_por_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[concluido_por],
    )
