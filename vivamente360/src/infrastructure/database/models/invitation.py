import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign


class Invitation(Base, TimestampMixin):
    """Convite de participação — Blind Drop: email cifrado, sem FK para resposta."""

    __tablename__ = "invitations"

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
    # Email do convidado cifrado com AES-256-GCM — nunca em plaintext no banco
    email_criptografado: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    # SHA-256 do token de convite — usado para validar sem expor o token
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, nullable=False)
    respondido: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    # Relationship — sem FK reversa para survey_responses (Blind Drop)
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="invitations")
