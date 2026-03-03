from enum import Enum


class TaskQueueStatus(str, Enum):
    """Estados de processamento de uma tarefa na fila PostgreSQL."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
