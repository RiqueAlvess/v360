import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums.task_queue_status import TaskQueueStatus
from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.models.base import Base, TimestampMixin


class TaskQueue(Base, TimestampMixin):
    """Fila de tarefas assíncronas em PostgreSQL — usa SELECT FOR UPDATE SKIP LOCKED."""

    __tablename__ = "task_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tipo: Mapped[TaskQueueType] = mapped_column(
        sa.Enum(TaskQueueType, name="task_queue_type"),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[TaskQueueStatus] = mapped_column(
        sa.Enum(TaskQueueStatus, name="task_queue_status"),
        nullable=False,
        default=TaskQueueStatus.PENDING,
    )
    tentativas: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    agendado_para: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Índice composto para performance do worker (filtra por status + ordena por agendado_para)
    __table_args__ = (
        sa.Index("ix_task_queue_status_agendado_para", "status", "agendado_para"),
    )
