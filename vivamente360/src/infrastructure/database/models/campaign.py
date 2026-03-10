import uuid
from datetime import date
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.campaign_status import CampaignStatus
from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.invitation import Invitation
    from src.infrastructure.database.models.survey_response import SurveyResponse


class Campaign(Base, TimestampMixin):
    """Campanha de avaliação psicossocial vinculada a uma empresa."""

    __tablename__ = "campaigns"

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
    nome: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        sa.Enum(CampaignStatus, name="campaign_status", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CampaignStatus.DRAFT,
    )
    data_inicio: Mapped[date] = mapped_column(sa.Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(sa.Date, nullable=False)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="campaigns")
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation", back_populates="campaign"
    )
    survey_responses: Mapped[list["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="campaign"
    )
