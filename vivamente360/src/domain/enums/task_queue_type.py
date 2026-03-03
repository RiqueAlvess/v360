from enum import Enum


class TaskQueueType(str, Enum):
    """Tipos de tarefas processadas pela fila assíncrona."""

    COMPUTE_SCORES = "compute_scores"
    SEND_EMAIL = "send_email"
    SEND_INVITATIONS = "send_invitations"
    GENERATE_REPORT = "generate_report"
    CLEANUP_EXPIRED_TOKENS = "cleanup_expired_tokens"
