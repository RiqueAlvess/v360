import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.job_position import JobPosition
    from src.infrastructure.database.models.organizational_unit import OrganizationalUnit
    from src.infrastructure.database.models.sector import Sector


class DimEstrutura(Base):
    """Dimensão de estrutura organizacional do modelo estrela.

    Armazena um snapshot da hierarquia (empresa/unidade/setor/cargo) no momento
    do cálculo. Preserva histórico mesmo após renomeações ou reorganizações.
    """

    __tablename__ = "dim_estrutura"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # FKs opcionais — campanhas podem não ter estrutura organizacional definida
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
    cargo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("job_positions.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshots de nomes — preservam histórico após renomeações
    unidade_nome: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    setor_nome: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)
    cargo_nome: Mapped[Optional[str]] = mapped_column(sa.String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    unidade: Mapped[Optional["OrganizationalUnit"]] = relationship("OrganizationalUnit")
    setor: Mapped[Optional["Sector"]] = relationship("Sector")
    cargo: Mapped[Optional["JobPosition"]] = relationship("JobPosition")
