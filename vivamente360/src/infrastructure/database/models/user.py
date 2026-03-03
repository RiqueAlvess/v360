import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.user_role import UserRole
from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.refresh_token import RefreshToken


class User(Base, TimestampMixin):
    """Usuário da plataforma — email armazenado criptografado (AES-256-GCM)."""

    __tablename__ = "users"

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
    # SHA-256 hex digest do email em plaintext — para lookups sem expor o email
    email_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    # Email cifrado com AES-256-GCM — nunca em plaintext no banco
    email_criptografado: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        sa.Enum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.RESPONDENT,
    )
    ativo: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)

    # Relationships
    company: Mapped["Company"] = relationship("Company", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user"
    )

    __table_args__ = (
        sa.UniqueConstraint("company_id", "email_hash", name="uq_users_company_email"),
        sa.Index("ix_users_email_hash", "email_hash"),
    )
