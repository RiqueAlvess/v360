"""Repositório de registros de auditoria de email (email_logs).

Segue o padrão Repository do projeto: interface abstrata + implementação SQLAlchemy.
NUNCA armazena ou recebe emails em plaintext — apenas o hash SHA-256 do destinatário.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.email_log_status import EmailLogStatus
from src.infrastructure.database.models.email_log import EmailLog


class EmailLogRepository(ABC):
    """Interface abstrata do repositório de logs de email."""

    @abstractmethod
    async def create(
        self,
        tipo: str,
        destinatario_hash: str,
    ) -> EmailLog:
        """Cria um registro de email_log com status PENDING.

        Args:
            tipo: Tipo do email (ex: 'invitation_email').
            destinatario_hash: SHA-256 hex do email destinatário — NUNCA plaintext.

        Returns:
            Instância de EmailLog criada e persistida.
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        log_id: UUID,
        status: EmailLogStatus,
        provider_id: Optional[str] = None,
    ) -> None:
        """Atualiza o status de um registro de email_log.

        Args:
            log_id: UUID do registro a atualizar.
            status: Novo status (SENT, FAILED, BOUNCED).
            provider_id: ID retornado pelo provedor Resend após envio bem-sucedido.
        """
        ...

    @abstractmethod
    async def count_recent_by_hash(
        self,
        destinatario_hash: str,
        hours: int = 24,
    ) -> int:
        """Conta emails enviados ao mesmo destinatário nas últimas N horas.

        Usado pelo EmailService para aplicar rate limiting (máximo 3 por 24h).

        Args:
            destinatario_hash: SHA-256 hex do email destinatário.
            hours: Janela de tempo para contagem (padrão: 24 horas).

        Returns:
            Número de registros encontrados na janela de tempo.
        """
        ...


class SQLEmailLogRepository(EmailLogRepository):
    """Implementação SQLAlchemy do repositório de logs de email."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        tipo: str,
        destinatario_hash: str,
    ) -> EmailLog:
        log = EmailLog(
            tipo=tipo,
            destinatario_hash=destinatario_hash,
            status=EmailLogStatus.PENDING,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def update_status(
        self,
        log_id: UUID,
        status: EmailLogStatus,
        provider_id: Optional[str] = None,
    ) -> None:
        values: dict[str, object] = {"status": status}
        if provider_id is not None:
            values["provider_id"] = provider_id

        await self._session.execute(
            update(EmailLog)
            .where(EmailLog.id == log_id)
            .values(**values)
        )
        await self._session.flush()

    async def count_recent_by_hash(
        self,
        destinatario_hash: str,
        hours: int = 24,
    ) -> int:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        result = await self._session.execute(
            select(func.count())
            .select_from(EmailLog)
            .where(
                EmailLog.destinatario_hash == destinatario_hash,
                EmailLog.created_at >= cutoff,
            )
        )
        return result.scalar_one()
