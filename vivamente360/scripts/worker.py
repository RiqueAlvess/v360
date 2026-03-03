#!/usr/bin/env python3
"""Entrypoint do worker de tarefas assíncronas — VIVAMENTE 360º.

Uso:
    python scripts/worker.py

O worker executa em loop infinito, consumindo tarefas da tabela task_queue
via SELECT FOR UPDATE SKIP LOCKED. Múltiplos workers podem ser iniciados
em paralelo sem risco de processar a mesma tarefa.

Handlers registrados:
    - send_email        → SendEmailHandler
    - compute_scores    → RebuildAnalyticsHandler
    - cleanup_expired_tokens → (handler inline: TokenRepository.cleanup_expired)

Para rodar múltiplos workers em produção:
    # Opção 1: processos separados
    python scripts/worker.py &
    python scripts/worker.py &

    # Opção 2: via docker-compose scale
    docker-compose up --scale worker=3
"""
import asyncio
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Garantir que o pacote 'src' seja importável ao executar via linha de comando
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.domain.enums.task_queue_type import TaskQueueType  # noqa: E402
from src.infrastructure.database.session import AsyncSessionLocal  # noqa: E402
from src.infrastructure.queue.handlers.rebuild_analytics_handler import (  # noqa: E402
    RebuildAnalyticsHandler,
)
from src.infrastructure.queue.handlers.send_email_handler import (  # noqa: E402
    SendEmailHandler,
)
from src.infrastructure.queue.worker import TaskWorker  # noqa: E402
from src.infrastructure.repositories.token_repository import (  # noqa: E402
    SQLTokenRepository,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("worker")

# Intervalo de polling quando a fila está vazia (segundos)
_POLL_INTERVAL: float = 1.0


class CleanupTokensHandler:
    """Handler inline para limpeza de tokens expirados.

    Não herda de BaseTaskHandler pois é criado diretamente aqui para
    evitar dependências circulares com infraestrutura de auth.
    """

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self._db = db

    async def execute(self, payload: dict) -> None:  # type: ignore[type-arg]
        """Remove tokens de refresh expirados do banco de dados."""
        repo = SQLTokenRepository(self._db)
        count = await repo.cleanup_expired()
        logger.info("Tokens expirados removidos: %d", count)


async def main() -> None:
    """Inicializa o worker, registra handlers e inicia o loop de processamento."""
    logger.info("Iniciando worker VIVAMENTE 360º…")

    async with AsyncSessionLocal() as session:
        worker = TaskWorker(db=session)

        # Registrar todos os handlers disponíveis
        worker.register(TaskQueueType.SEND_EMAIL.value, SendEmailHandler)
        worker.register(TaskQueueType.COMPUTE_SCORES.value, RebuildAnalyticsHandler)
        worker.register(
            TaskQueueType.CLEANUP_EXPIRED_TOKENS.value,
            CleanupTokensHandler,  # type: ignore[arg-type]
        )

        logger.info(
            "Handlers registrados: %s",
            [
                TaskQueueType.SEND_EMAIL.value,
                TaskQueueType.COMPUTE_SCORES.value,
                TaskQueueType.CLEANUP_EXPIRED_TOKENS.value,
            ],
        )

        await worker.run_forever(interval_seconds=_POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker encerrado pelo usuário.")
