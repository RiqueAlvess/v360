import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.company_plan import CompanyPlan
from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign
    from src.infrastructure.database.models.user import User


class Company(Base, TimestampMixin):
    """Empresa contratante da plataforma — raiz do isolamento multi-tenant."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cnpj: Mapped[str] = mapped_column(sa.String(18), unique=True, nullable=False)
    plano: Mapped[CompanyPlan] = mapped_column(
        sa.Enum(CompanyPlan, name="company_plan"),
        nullable=False,
        default=CompanyPlan.FREE,
    )
    ativo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="company")
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign", back_populates="company"
    )
