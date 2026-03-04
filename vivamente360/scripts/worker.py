#!/usr/bin/env python3
"""Entrypoint do worker de tarefas assíncronas — VIVAMENTE 360º.

Uso:
    python scripts/worker.py

O worker executa em loop infinito, consumindo tarefas da tabela task_queue
via SELECT FOR UPDATE SKIP LOCKED. Múltiplos workers podem ser iniciados
em paralelo sem risco de processar a mesma tarefa.

Handlers registrados:
    - send_email                      → SendEmailHandler
    - compute_scores                  → RebuildAnalyticsHandler
    - analyze_sentiment               → AnalyzeSentimentHandler
    - run_ai_analysis                 → RunAiAnalysisHandler
    - notify_plan_completed           → NotifyPlanCompletedHandler
    - cleanup_expired_tokens          → (handler inline: TokenRepository.cleanup_expired)
    - refresh_campaign_comparison     → RefreshCampaignComparisonHandler (Módulo 09)

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
from src.infrastructure.queue.handlers.analyze_sentiment_handler import (  # noqa: E402
    AnalyzeSentimentHandler,
)
from src.infrastructure.queue.handlers.notify_plan_completed_handler import (  # noqa: E402
    NotifyPlanCompletedHandler,
)
from src.infrastructure.queue.handlers.rebuild_analytics_handler import (  # noqa: E402
    RebuildAnalyticsHandler,
)
from src.infrastructure.queue.handlers.refresh_campaign_comparison_handler import (  # noqa: E402
    RefreshCampaignComparisonHandler,
)
from src.infrastructure.queue.handlers.run_ai_analysis_handler import (  # noqa: E402
    RunAiAnalysisHandler,
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
        worker.register(TaskQueueType.ANALYZE_SENTIMENT.value, AnalyzeSentimentHandler)
        worker.register(
            TaskQueueType.CLEANUP_EXPIRED_TOKENS.value,
            CleanupTokensHandler,  # type: ignore[arg-type]
        )
        worker.register(
            TaskQueueType.NOTIFY_PLAN_COMPLETED.value,
            NotifyPlanCompletedHandler,
        )
        worker.register(TaskQueueType.RUN_AI_ANALYSIS.value, RunAiAnalysisHandler)
        # Módulo 09: refresh da view materializada campaign_comparison
        worker.register(
            TaskQueueType.REFRESH_CAMPAIGN_COMPARISON.value,
            RefreshCampaignComparisonHandler,
        )

        logger.info(
            "Handlers registrados: %s",
            [
                TaskQueueType.SEND_EMAIL.value,
                TaskQueueType.COMPUTE_SCORES.value,
                TaskQueueType.ANALYZE_SENTIMENT.value,
                TaskQueueType.CLEANUP_EXPIRED_TOKENS.value,
                TaskQueueType.NOTIFY_PLAN_COMPLETED.value,
                TaskQueueType.RUN_AI_ANALYSIS.value,
                TaskQueueType.REFRESH_CAMPAIGN_COMPARISON.value,
            ],
        )

        await worker.run_forever(interval_seconds=_POLL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker encerrado pelo usuário.")
