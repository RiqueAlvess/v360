"""Worker que processa tarefas da fila PostgreSQL usando SELECT FOR UPDATE SKIP LOCKED."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.queue.models import TaskQueue, TaskQueueStatus

logger = logging.getLogger(__name__)

# Número máximo de caracteres do traceback persistido em task_queue.erro
_MAX_ERRO_LENGTH: int = 2000


class TaskWorker:
    """Processa tarefas da fila PostgreSQL de forma concorrente e segura.

    O padrão SELECT FOR UPDATE SKIP LOCKED garante que dois workers rodando
    simultaneamente nunca processem a mesma tarefa. Tarefas com erro são
    reagendadas com backoff exponencial até atingir max_tentativas, quando
    então recebem status FAILED.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._handlers: dict[str, type[BaseTaskHandler]] = {}

    def register(self, tipo: str, handler: type[BaseTaskHandler]) -> None:
        """Associa um tipo de tarefa ao seu handler.

        Args:
            tipo: Valor string do enum TaskQueueType (ex: 'send_email').
            handler: Classe (não instância) que implementa BaseTaskHandler.
        """
        self._handlers[tipo] = handler
        logger.debug("Handler registrado: %s → %s", tipo, handler.__name__)

    async def process_next(self) -> Optional[bool]:
        """Busca e processa a próxima tarefa pendente disponível.

        Usa SELECT FOR UPDATE SKIP LOCKED para garantir que workers
        concorrentes não processem a mesma tarefa.

        Returns:
            True se uma tarefa foi processada, None se não há tarefas pendentes.
        """
        stmt = (
            select(TaskQueue)
            .where(TaskQueue.status == TaskQueueStatus.PENDING)
            .where(TaskQueue.agendado_para <= func.now())
            .order_by(TaskQueue.agendado_para)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        task = (await self._db.execute(stmt)).scalar_one_or_none()
        if not task:
            return None

        await self._execute_task(task)
        return True

    async def _execute_task(self, task: TaskQueue) -> None:
        """Executa uma tarefa, gerencia status e aplica retry com backoff exponencial.

        Fluxo:
            1. Marca a tarefa como PROCESSING e persiste (commit imediato).
            2. Instancia o handler e chama execute(payload).
            3. Sucesso → status COMPLETED + concluido_em.
            4. Falha → rollback das mudanças do handler, incrementa tentativas,
               reagenda (PENDING) ou finaliza (FAILED) conforme max_tentativas.
        """
        handler_class = self._handlers.get(task.tipo.value)

        # Marca como PROCESSING antes de qualquer operação do handler
        task.status = TaskQueueStatus.PROCESSING
        task.iniciado_em = datetime.now(tz=timezone.utc)
        await self._db.commit()

        if handler_class is None:
            logger.error(
                "Nenhum handler registrado para tipo '%s' (task_id=%s)",
                task.tipo.value,
                task.id,
            )
            task.status = TaskQueueStatus.FAILED
            task.erro = f"Handler não registrado para tipo: {task.tipo.value}"
            task.concluido_em = datetime.now(tz=timezone.utc)
            await self._db.commit()
            return

        try:
            handler = handler_class(self._db)
            await handler.execute(task.payload)

            task.status = TaskQueueStatus.COMPLETED
            task.concluido_em = datetime.now(tz=timezone.utc)
            await self._db.commit()

            logger.info(
                "Task concluída com sucesso: id=%s tipo=%s",
                task.id,
                task.tipo.value,
            )

        except Exception as exc:
            # Rollback das mudanças feitas pelo handler, mas o PROCESSING já foi committed
            await self._db.rollback()

            # Após rollback os atributos ficam expirados — recarregar do banco
            await self._db.refresh(task)

            task.tentativas += 1
            task.erro = str(exc)[:_MAX_ERRO_LENGTH]

            if task.tentativas >= task.max_tentativas:
                task.status = TaskQueueStatus.FAILED
                task.concluido_em = datetime.now(tz=timezone.utc)
                logger.error(
                    "Task FAILED após %d tentativas: id=%s tipo=%s erro=%s",
                    task.tentativas,
                    task.id,
                    task.tipo.value,
                    task.erro,
                )
            else:
                # Backoff exponencial: 2^tentativas segundos (2s, 4s, 8s…)
                backoff_seconds = 2 ** task.tentativas
                task.status = TaskQueueStatus.PENDING
                task.agendado_para = datetime.now(tz=timezone.utc) + timedelta(
                    seconds=backoff_seconds
                )
                logger.warning(
                    "Task reagendada em %ds: id=%s tipo=%s tentativa=%d/%d",
                    backoff_seconds,
                    task.id,
                    task.tipo.value,
                    task.tentativas,
                    task.max_tentativas,
                )

            await self._db.commit()

    async def run_forever(self, interval_seconds: float = 1.0) -> None:
        """Loop principal do worker — processa tarefas continuamente.

        Quando não há tarefas pendentes, dorme por interval_seconds antes
        de verificar novamente, evitando polling excessivo.

        Args:
            interval_seconds: Tempo de espera entre verificações quando a fila está vazia.
        """
        logger.info("Worker iniciado. Aguardando tarefas (poll=%.1fs)…", interval_seconds)
        while True:
            try:
                processed = await self.process_next()
                if not processed:
                    await asyncio.sleep(interval_seconds)
            except Exception:
                logger.exception("Erro inesperado no loop do worker — reiniciando ciclo")
                await asyncio.sleep(interval_seconds)
