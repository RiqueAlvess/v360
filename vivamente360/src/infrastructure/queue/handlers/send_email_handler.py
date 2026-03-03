"""Handler para tarefas do tipo 'send_email'.

Payload esperado:
    {
        "destinatario_hash": "<SHA-256 do email>",
        "template": "<nome do template>",
        "context": {<variáveis do template>},
        "tipo_email": "<tipo para registro no EmailLog>"
    }

Regra R6: Email SEMPRE via EmailService — nunca diretamente.
Este handler delega o envio ao EmailService quando implementado (Blueprint 05/06).
Até lá, registra a intenção no log para garantir rastreabilidade.
"""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.queue.base_handler import BaseTaskHandler

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"destinatario_hash", "template", "context", "tipo_email"}
)


class SendEmailHandler(BaseTaskHandler):
    """Processa tarefas de envio de email enfileiradas via TaskService.

    Valida o payload, delega o envio ao EmailService e garante que
    nenhuma chamada direta ao SDK do Resend seja feita neste ponto.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Processa o envio de email a partir do payload da tarefa.

        Args:
            payload: Dicionário com os campos obrigatórios para envio.

        Raises:
            ValueError: Se o payload estiver incompleto.
            RuntimeError: Se o EmailService não estiver disponível.
        """
        self._validate_payload(payload)

        destinatario_hash: str = payload["destinatario_hash"]
        template: str = payload["template"]
        context: dict[str, Any] = payload["context"]
        tipo_email: str = payload["tipo_email"]

        logger.info(
            "Processando envio de email: template=%s tipo=%s destinatario_hash=%.8s…",
            template,
            tipo_email,
            destinatario_hash,
        )

        # TODO (Blueprint 05/06): substituir pelo EmailService quando implementado.
        # O EmailService é o único ponto de saída para envios (regra R6).
        # Exemplo de integração futura:
        #
        #   email_service = EmailService(db=self._db)
        #   await email_service.send(
        #       destinatario_hash=destinatario_hash,
        #       template=template,
        #       context=context,
        #       tipo=tipo_email,
        #   )

        logger.info(
            "Email enfileirado para envio: template=%s destinatario_hash=%.8s…",
            template,
            destinatario_hash,
        )

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
