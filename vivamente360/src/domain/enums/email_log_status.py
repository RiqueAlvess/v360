from enum import Enum


class EmailLogStatus(str, Enum):
    """Status de envio registrado nos logs de email."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
