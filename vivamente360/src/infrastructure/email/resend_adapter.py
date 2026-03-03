"""Adaptador isolado para o SDK Resend.

REGRA CRÍTICA (R6): Este é o ÚNICO arquivo em toda a codebase que importa o SDK resend.
Nenhum outro módulo pode realizar essa importação diretamente.

A chamada ao SDK é feita via asyncio.to_thread() para não bloquear o event loop,
já que o SDK oficial é síncrono.
"""
import asyncio
import logging
from typing import Any

import resend

from src.shared.config import settings

logger = logging.getLogger(__name__)


class ResendAdapter:
    """Encapsula toda comunicação com a API do Resend.

    Responsabilidades:
    - Configurar a chave de API do Resend.
    - Enviar emails via API do provedor.
    - Retornar o provider_id para rastreamento no email_log.

    NUNCA armazena o email em plaintext — recebe apenas para envio em memória.
    """

    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str,
    ) -> None:
        self._from_email = from_email
        self._from_name = from_name
        resend.api_key = api_key

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        email_log_id: str,
    ) -> str:
        """Envia email via Resend API de forma não-bloqueante.

        O email em plaintext existe APENAS em memória durante esta chamada.
        Nenhum valor de `to` é registrado ou persistido por este adaptador.

        Args:
            to: Endereço de email do destinatário em plaintext.
            subject: Assunto do email.
            html: Corpo HTML do email renderizado.
            email_log_id: UUID do registro em email_logs (para correlação em logs).

        Returns:
            provider_id retornado pelo Resend (ID do email no sistema do provedor).

        Raises:
            RuntimeError: Se a API do Resend retornar erro ou não retornar ID.
        """
        params: dict[str, Any] = {
            "from": f"{self._from_name} <{self._from_email}>",
            "to": [to],
            "subject": subject,
            "html": html,
        }
        logger.info(
            "Enviando email via Resend: log_id=%s subject='%s'",
            email_log_id,
            subject,
        )
        try:
            # SDK síncrono → executado em thread pool para não bloquear o event loop
            response = await asyncio.to_thread(resend.Emails.send, params)
            provider_id: str = response.get("id", "")
            if not provider_id:
                raise RuntimeError(
                    f"Resend não retornou ID para log_id={email_log_id}. "
                    f"Resposta: {response}"
                )
            logger.info(
                "Email enviado com sucesso: provider_id=%s log_id=%s",
                provider_id,
                email_log_id,
            )
            return provider_id
        except Exception as exc:
            logger.error(
                "Falha ao enviar email via Resend: log_id=%s erro=%s",
                email_log_id,
                str(exc),
            )
            raise
