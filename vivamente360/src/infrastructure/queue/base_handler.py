"""Classe base abstrata para todos os handlers de tarefas da fila."""
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class BaseTaskHandler(ABC):
    """Define o contrato que todo handler de tarefa deve implementar.

    Cada subclasse é responsável por processar um tipo específico de tarefa
    da fila PostgreSQL. O worker instancia o handler com a sessão de banco
    e chama execute() com o payload da tarefa.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @abstractmethod
    async def execute(self, payload: dict[str, Any]) -> None:
        """Processa a tarefa com o payload fornecido.

        Args:
            payload: Dicionário JSONB extraído do campo task_queue.payload.

        Raises:
            Exception: Qualquer exceção propaga para o worker, que trata
                       o retry e atualiza o status da tarefa.
        """
        ...
