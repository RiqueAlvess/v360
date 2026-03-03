import uuid
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.organizational_unit import OrganizationalUnit


class Sector(Base, TimestampMixin):
    """Setor dentro de uma unidade organizacional (ex: RH, TI, Financeiro)."""

    __tablename__ = "sectors"

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
    unidade_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    ativo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="sectors")
    unidade: Mapped[Optional["OrganizationalUnit"]] = relationship(
        "OrganizationalUnit", back_populates="sectors"
    )
