import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums.email_log_status import EmailLogStatus
from src.infrastructure.database.models.base import Base


class EmailLog(Base):
    """Registro de auditoria de emails enviados via EmailService."""

    __tablename__ = "email_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tipo: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    # SHA-256 hex do email destinatário — nunca o email em plaintext
    destinatario_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[EmailLogStatus] = mapped_column(
        sa.Enum(EmailLogStatus, name="email_log_status", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    # ID retornado pelo provedor (Resend) — pode ser nulo em caso de falha pré-envio
    provider_id: Mapped[Optional[str]] = mapped_column(
        sa.String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
