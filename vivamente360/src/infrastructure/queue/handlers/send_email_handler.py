"""Handler para tarefas do tipo 'send_email'.

Payload esperado:
    {
        "email_log_id": "<UUID do registro em email_logs>",
        "destinatario_hash": "<SHA-256 do email>",
        "destinatario_criptografado": "<AES-256-GCM base64 do email>",
        "template": "<nome do template>",
        "context": {<variáveis do template>},
        "tipo_email": "<tipo para registro no EmailLog>"
    }

Regra R6: Email SEMPRE via ResendAdapter — nunca diretamente pelo SDK resend.
O email plaintext é decifrado em memória apenas para envio e descartado imediatamente.
"""
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.email_log_status import EmailLogStatus
from src.infrastructure.email.resend_adapter import ResendAdapter
from src.infrastructure.email.template_renderer import TemplateRenderer
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.repositories.email_log_repository import SQLEmailLogRepository
from src.shared.config import settings
from src.shared.security import decrypt_data

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "email_log_id",
        "destinatario_hash",
        "destinatario_criptografado",
        "template",
        "context",
        "tipo_email",
    }
)


class SendEmailHandler(BaseTaskHandler):
    """Processa tarefas de envio de email enfileiradas via EmailService.

    Fluxo de execução:
        1. Valida payload.
        2. Decifra email AES-256-GCM → plaintext (apenas em memória).
        3. Renderiza template HTML com o contexto.
        4. Chama ResendAdapter.send() com o email em plaintext.
        5. Atualiza email_log com status SENT e provider_id.
        6. Em caso de falha, atualiza email_log com status FAILED e relança.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._resend = ResendAdapter(
            api_key=settings.RESEND_API_KEY,
            from_email=settings.EMAIL_FROM,
            from_name=settings.EMAIL_FROM_NAME,
        )
        self._renderer = TemplateRenderer()
        self._email_log_repo = SQLEmailLogRepository(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Processa o envio de email a partir do payload da tarefa.

        Args:
            payload: Dicionário com os campos obrigatórios para envio.

        Raises:
            ValueError: Se o payload estiver incompleto.
            RuntimeError: Se o ResendAdapter falhar no envio.
        """
        self._validate_payload(payload)

        email_log_id: UUID = UUID(payload["email_log_id"])
        destinatario_criptografado: str = payload["destinatario_criptografado"]
        template: str = payload["template"]
        context: dict[str, Any] = payload["context"]

        logger.info(
            "Processando envio de email: template=%s log_id=%s destinatario_hash=%.8s…",
            template,
            email_log_id,
            payload["destinatario_hash"],
        )

        try:
            # Decifra o email — plaintext existe APENAS em memória durante este bloco
            destinatario_plaintext = decrypt_data(
                destinatario_criptografado,
                settings.ENCRYPTION_KEY,
            )

            subject, html_body = self._renderer.render(template, context)

            provider_id = await self._resend.send(
                to=destinatario_plaintext,
                subject=subject,
                html=html_body,
                email_log_id=str(email_log_id),
            )

            await self._email_log_repo.update_status(
                log_id=email_log_id,
                status=EmailLogStatus.SENT,
                provider_id=provider_id,
            )

            logger.info(
                "Email enviado e log atualizado: log_id=%s provider_id=%s",
                email_log_id,
                provider_id,
            )

        except Exception as exc:
            # Atualiza o log como FAILED — o worker cuidará do retry (backoff exponencial)
            await self._email_log_repo.update_status(
                log_id=email_log_id,
                status=EmailLogStatus.FAILED,
            )
            logger.error(
                "Falha no envio de email: log_id=%s erro=%s",
                email_log_id,
                str(exc),
            )
            raise

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Verifica que todos os campos obrigatórios estão presentes no payload.

        Args:
            payload: Payload recebido da tarefa.

        Raises:
            ValueError: Se algum campo obrigatório estiver ausente.
        """
        missing = _REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Payload inválido para send_email. Campos ausentes: {sorted(missing)}"
            )
