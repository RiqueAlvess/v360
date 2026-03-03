"""EmailService — middleware de email da plataforma VIVAMENTE 360°.

REGRA R6: Este service é o ÚNICO ponto de entrada para envio de emails.
Nenhum módulo do sistema chama o SDK Resend diretamente.

Fluxo completo:
    Qualquer módulo
        ↓ chama
    EmailService.send(tipo, destinatario_email, contexto)
        ↓ hash do email para rate limit
        ↓ valida rate limit (máx 3/24h por destinatário)
        ↓ cria registro em email_logs (status=PENDING)
        ↓ cifra email com AES-256-GCM para o payload da task
    TaskService.enqueue(SEND_EMAIL, payload)
        ↓ worker processa
    SendEmailHandler → ResendAdapter → Resend API
        ↓ atualiza email_logs.status
"""
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.email_log_repository import (
    EmailLogRepository,
    SQLEmailLogRepository,
)
from src.shared.config import settings
from src.shared.exceptions import RateLimitError
from src.shared.security import encrypt_data, hash_token

logger = logging.getLogger(__name__)

# Máximo de emails enviados ao mesmo destinatário em 24 horas
MAX_EMAILS_PER_24H: int = 3


class EmailService:
    """Orquestra o envio de emails com auditoria, rate limiting e fila assíncrona.

    Responsabilidades:
    - Receber pedidos de envio de qualquer módulo da aplicação.
    - Aplicar rate limiting por destinatário (máximo 3 por 24h).
    - Registrar a intenção de envio em email_logs (LGPD: apenas hash do destinatário).
    - Cifrar o email com AES-256-GCM para transporte seguro via task queue.
    - Delegar o envio efetivo ao SendEmailHandler via TaskService.

    Não acessa o SDK Resend — isso é responsabilidade do ResendAdapter.
    """

    def __init__(
        self,
        db: AsyncSession,
        email_log_repo: EmailLogRepository | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self._db = db
        self._email_log_repo: EmailLogRepository = (
            email_log_repo or SQLEmailLogRepository(db)
        )
        self._task_service: TaskService = task_service or TaskService(db)

    async def send(
        self,
        tipo: str,
        destinatario_email: str,
        contexto: dict[str, Any],
    ) -> UUID:
        """Valida, registra e enfileira um email para envio assíncrono.

        O email plaintext é cifrado com AES-256-GCM antes de entrar na task queue.
        O banco de dados nunca armazena o email em plaintext — apenas o hash SHA-256.

        Args:
            tipo: Tipo do email (deve corresponder a um EmailTemplateType value).
            destinatario_email: Email do destinatário em plaintext. Usado apenas
                                em memória — nunca persiste no banco.
            contexto: Variáveis para renderização do template HTML.

        Returns:
            UUID do registro email_log criado (status=PENDING).

        Raises:
            RateLimitError: Se o destinatário já recebeu 3 ou mais emails nas
                            últimas 24 horas.
        """
        destinatario_hash = hash_token(destinatario_email.lower().strip())

        await self._check_rate_limit(destinatario_hash)

        email_log = await self._email_log_repo.create(
            tipo=tipo,
            destinatario_hash=destinatario_hash,
        )

        # Cifra email com AES-256-GCM — plaintext nunca entra no banco de dados
        destinatario_criptografado = encrypt_data(
            destinatario_email,
            settings.ENCRYPTION_KEY,
        )

        await self._task_service.enqueue(
            tipo=TaskQueueType.SEND_EMAIL,
            payload={
                "email_log_id": str(email_log.id),
                "destinatario_hash": destinatario_hash,
                "destinatario_criptografado": destinatario_criptografado,
                "template": tipo,
                "context": contexto,
                "tipo_email": tipo,
            },
        )

        logger.info(
            "Email enfileirado: tipo=%s log_id=%s destinatario_hash=%.8s…",
            tipo,
            email_log.id,
            destinatario_hash,
        )

        return email_log.id

    async def _check_rate_limit(self, destinatario_hash: str) -> None:
        """Verifica se o destinatário atingiu o limite de 3 emails em 24h.

        Args:
            destinatario_hash: SHA-256 hex do email destinatário.

        Raises:
            RateLimitError: Se a contagem atingir ou superar MAX_EMAILS_PER_24H.
        """
        count = await self._email_log_repo.count_recent_by_hash(
            destinatario_hash, hours=24
        )
        if count >= MAX_EMAILS_PER_24H:
            logger.warning(
                "Rate limit atingido para destinatário hash=%.8s… (%d emails em 24h)",
                destinatario_hash,
                count,
            )
            raise RateLimitError(
                f"Limite de {MAX_EMAILS_PER_24H} emails por 24h atingido para este destinatário."
            )
