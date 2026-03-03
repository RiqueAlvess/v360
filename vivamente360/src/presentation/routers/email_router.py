"""Router para webhooks de status do Resend.

Recebe eventos de entrega enviados pelo Resend (via svix) e atualiza o status
dos registros em email_logs. Garante rastreabilidade completa do ciclo de vida
de cada email enviado.

Eventos suportados:
    email.delivered → EmailLogStatus.SENT
    email.bounced   → EmailLogStatus.BOUNCED
    email.complained → EmailLogStatus.BOUNCED
    Outros eventos são registrados em log e ignorados.

Segurança:
    O segredo configurado em RESEND_WEBHOOK_SECRET é comparado com o header
    X-Webhook-Secret enviado pelo Resend para autenticar a origem do webhook.
"""
import hashlib
import hmac
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.email_log_status import EmailLogStatus
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.email_log_repository import SQLEmailLogRepository
from src.shared.config import settings

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/webhooks/email", tags=["webhooks"])

# Mapeamento de evento Resend → status no email_log
_EVENT_TO_STATUS: dict[str, EmailLogStatus] = {
    "email.delivered": EmailLogStatus.SENT,
    "email.bounced": EmailLogStatus.BOUNCED,
    "email.complained": EmailLogStatus.BOUNCED,
}


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    summary="Webhook de status de email (Resend)",
    description=(
        "Recebe eventos de entrega do Resend e atualiza o status em email_logs. "
        "Requer o header X-Webhook-Secret com o segredo configurado."
    ),
)
async def resend_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> dict[str, str]:
    """Processa eventos de webhook enviados pelo Resend.

    O Resend envia este webhook quando o status de entrega de um email muda.
    O `data.email_id` é o `provider_id` registrado em email_logs.

    Args:
        request: Request FastAPI com o corpo JSON do evento.
        db: Sessão assíncrona do banco de dados.
        x_webhook_secret: Secret header para validar a origem do webhook.

    Returns:
        Dicionário com o status de processamento.

    Raises:
        HTTPException 401: Se o segredo do webhook for inválido.
        HTTPException 422: Se o payload não contiver os campos esperados.
    """
    _verify_webhook_secret(x_webhook_secret)

    body: dict[str, Any] = await request.json()
    event_type: str = body.get("type", "")
    data: dict[str, Any] = body.get("data", {})
    provider_id: str = data.get("email_id", "")

    logger.info(
        "Webhook Resend recebido: type=%s provider_id=%s",
        event_type,
        provider_id,
    )

    new_status = _EVENT_TO_STATUS.get(event_type)
    if new_status is None:
        logger.debug("Evento Resend ignorado: type=%s", event_type)
        return {"status": "ignored", "event_type": event_type}

    if not provider_id:
        logger.warning("Webhook sem provider_id: type=%s body=%s", event_type, body)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Campo 'data.email_id' ausente no payload do webhook.",
        )

    await _update_log_by_provider_id(db, provider_id, new_status)

    return {"status": "processed", "event_type": event_type, "provider_id": provider_id}


def _verify_webhook_secret(received_secret: str | None) -> None:
    """Valida o segredo do webhook via comparação constante (timing-safe).

    Args:
        received_secret: Valor do header X-Webhook-Secret.

    Raises:
        HTTPException 401: Se o segredo for inválido ou ausente.
    """
    expected = settings.RESEND_WEBHOOK_SECRET
    if not received_secret or not hmac.compare_digest(
        hashlib.sha256(received_secret.encode()).hexdigest(),
        hashlib.sha256(expected.encode()).hexdigest(),
    ):
        logger.warning("Tentativa de webhook com segredo inválido.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Segredo de webhook inválido.",
        )


async def _update_log_by_provider_id(
    db: AsyncSession,
    provider_id: str,
    new_status: EmailLogStatus,
) -> None:
    """Busca o email_log pelo provider_id e atualiza o status.

    Args:
        db: Sessão assíncrona do banco de dados.
        provider_id: ID do email no sistema do Resend.
        new_status: Novo status a aplicar ao registro.
    """
    from sqlalchemy import select, update

    from src.infrastructure.database.models.email_log import EmailLog

    result = await db.execute(
        select(EmailLog.id).where(EmailLog.provider_id == provider_id)
    )
    log_id = result.scalar_one_or_none()

    if log_id is None:
        logger.warning(
            "Webhook recebido para provider_id desconhecido: %s", provider_id
        )
        return

    repo = SQLEmailLogRepository(db)
    await repo.update_status(log_id=log_id, status=new_status)
    await db.commit()

    logger.info(
        "email_log atualizado via webhook: log_id=%s provider_id=%s status=%s",
        log_id,
        provider_id,
        new_status.value,
    )
