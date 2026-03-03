import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company


class JobPosition(Base, TimestampMixin):
    """Cargo ou função de um respondente (ex: Analista, Gerente, Diretor)."""

    __tablename__ = "job_positions"

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
    nome: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    ativo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company", back_populates="job_positions"
    )
