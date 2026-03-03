"""Service para enfileirar e gerenciar tarefas assíncronas na fila PostgreSQL."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.models import TaskQueue, TaskQueueStatus, TaskQueueType


class TaskService:
    """Gerencia o ciclo de vida de tarefas na fila PostgreSQL.

    Responsabilidades:
    - Criar novas tarefas (enqueue) com suporte a delay opcional.
    - Cancelar tarefas ainda pendentes (cancel).

    Não processa tarefas — isso é responsabilidade do TaskWorker.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def enqueue(
        self,
        tipo: TaskQueueType,
        payload: dict[str, Any],
        delay_seconds: int = 0,
    ) -> TaskQueue:
        """Enfileira uma nova tarefa para processamento assíncrono.

        Args:
            tipo: Tipo da tarefa (enum TaskQueueType).
            payload: Dados necessários para o handler processar a tarefa.
            delay_seconds: Segundos a aguardar antes de disponibilizar para o worker.
                           0 significa disponível imediatamente.

        Returns:
            A instância de TaskQueue criada e persistida.
        """
        agendado_para = datetime.now(tz=timezone.utc)
        if delay_seconds > 0:
            agendado_para += timedelta(seconds=delay_seconds)

        task = TaskQueue(
            tipo=tipo,
            payload=payload,
            agendado_para=agendado_para,
        )
        self._db.add(task)
        await self._db.commit()
        await self._db.refresh(task)
        return task

    async def cancel(self, task_id: uuid.UUID) -> bool:
        """Cancela uma tarefa pendente.

        Apenas tarefas com status PENDING podem ser canceladas.
        Tarefas já em PROCESSING, COMPLETED ou FAILED não são afetadas.

        Args:
            task_id: UUID da tarefa a ser cancelada.

        Returns:
            True se a tarefa foi cancelada com sucesso.
            False se a tarefa não existe ou não está no status PENDING.
        """
        result = await self._db.execute(
            update(TaskQueue)
            .where(TaskQueue.id == task_id)
            .where(TaskQueue.status == TaskQueueStatus.PENDING)
            .values(status=TaskQueueStatus.CANCELLED)
        )
        await self._db.commit()
        return result.rowcount > 0
