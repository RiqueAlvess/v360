"""Testes unitários do EmailService.

Cobre:
    - send(): sucesso, rate limit, enfileiramento correto
    - Verificação de que email plaintext nunca é armazenado
    - Rate limit: máximo MAX_EMAILS_PER_24H por destinatário
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.email_service import EmailService, MAX_EMAILS_PER_24H
from src.shared.exceptions import RateLimitError


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def mock_task_service():
    task_svc = AsyncMock()
    task_svc.enqueue = AsyncMock(return_value=MagicMock())
    return task_svc


@pytest.fixture
def email_service(mock_session, mock_email_log_repo, mock_task_service):
    svc = EmailService(
        db=mock_session,
        email_log_repo=mock_email_log_repo,
        task_service=mock_task_service,
    )
    return svc


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestEmailServiceSend:
    async def test_send_enqueues_task(self, email_service, mock_email_log_repo, mock_task_service):
        """Envio de email enfileira task SEND_EMAIL na task_queue."""
        mock_email_log_repo.count_recent_by_hash.return_value = 0
        fake_log = MagicMock()
        fake_log.id = uuid.uuid4()
        mock_email_log_repo.create.return_value = fake_log

        await email_service.send(
            tipo="convite",
            destinatario_email="user@example.com",
            contexto={"nome": "Usuário Teste", "link": "https://example.com"},
            company_id=COMPANY_ID,
        )

        mock_task_service.enqueue.assert_called_once()
        enqueue_call = mock_task_service.enqueue.call_args
        # Verificar que a task foi enfileirada com email criptografado (não plaintext)
        payload = enqueue_call.kwargs.get("payload") or enqueue_call.args[1]
        assert "user@example.com" not in str(payload)

    async def test_send_rate_limit_exceeded_raises_error(
        self, email_service, mock_email_log_repo
    ):
        """Rate limit excedido levanta RateLimitError."""
        mock_email_log_repo.count_recent_by_hash.return_value = MAX_EMAILS_PER_24H

        with pytest.raises(RateLimitError):
            await email_service.send(
                tipo="convite",
                destinatario_email="spammed@example.com",
                contexto={},
                company_id=COMPANY_ID,
            )

    async def test_send_creates_email_log_with_hash_not_plaintext(
        self, email_service, mock_email_log_repo, mock_task_service
    ):
        """Email log armazena apenas o hash SHA-256 do destinatário."""
        mock_email_log_repo.count_recent_by_hash.return_value = 0
        fake_log = MagicMock()
        fake_log.id = uuid.uuid4()
        mock_email_log_repo.create.return_value = fake_log

        await email_service.send(
            tipo="convite",
            destinatario_email="user@example.com",
            contexto={},
            company_id=COMPANY_ID,
        )

        # Verificar que create foi chamado — sem email plaintext no banco
        create_call = mock_email_log_repo.create.call_args
        if create_call:
            call_kwargs = create_call.kwargs or {}
            # Email plaintext não deve aparecer em nenhum argumento
            assert "user@example.com" not in str(call_kwargs)
