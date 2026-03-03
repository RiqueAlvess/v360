"""Adaptador para a API OpenRouter — integração com LLMs via protocolo OpenAI.

Responsabilidade única: realizar a chamada HTTP à API OpenRouter e retornar
o resultado bruto. Não interpreta o conteúdo — isso é responsabilidade do handler.

Regra inviolável (Módulo 06):
    NUNCA instancie este adaptador diretamente em um request HTTP.
    Toda chamada passa pelo task_queue → RunAiAnalysisHandler.
"""
import logging
from typing import Any, Optional

import httpx

from src.shared.config import settings

logger = logging.getLogger(__name__)

# Timeout padrão para chamadas à API OpenRouter (LLMs podem ser lentos)
_REQUEST_TIMEOUT: float = 60.0

# Cabeçalhos obrigatórios para o OpenRouter identificar a aplicação
_DEFAULT_HEADERS: dict[str, str] = {
    "HTTP-Referer": "https://vivamente.com.br",
    "X-Title": "VIVAMENTE 360",
    "Content-Type": "application/json",
}


class OpenRouterAdapter:
    """Adaptador HTTP para a API OpenRouter (protocolo compatível com OpenAI).

    Encapsula a comunicação com o endpoint /chat/completions, injeta os
    cabeçalhos obrigatórios e normaliza os erros em exceções tipadas.

    Uso exclusivo via task_queue — jamais chamado durante um request HTTP.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        self._api_key: str = api_key or settings.OPENROUTER_API_KEY
        self._base_url: str = (base_url or settings.OPENROUTER_BASE_URL).rstrip("/")

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        """Envia uma requisição de chat completion à API OpenRouter.

        Args:
            messages: Lista de mensagens no formato OpenAI
                      [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].
            model: ID do modelo a utilizar (ex: 'openai/gpt-4o-mini').
                   Se None, usa settings.OPENROUTER_MODEL.
            max_tokens: Limite de tokens na resposta gerada.
            temperature: Criatividade (0.0 = determinístico, 1.0 = criativo).

        Returns:
            Dicionário com a resposta completa da API, incluindo:
            - choices[0].message.content: texto gerado
            - usage.prompt_tokens: tokens do prompt
            - usage.completion_tokens: tokens gerados
            - model: modelo efetivamente utilizado

        Raises:
            RuntimeError: Se a requisição HTTP falhar (4xx/5xx) ou ocorrer
                          erro de conexão/timeout.
        """
        selected_model: str = model or settings.OPENROUTER_MODEL

        request_body: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers: dict[str, str] = {
            **_DEFAULT_HEADERS,
            "Authorization": f"Bearer {self._api_key}",
        }

        logger.debug(
            "OpenRouter request: model=%s max_tokens=%d messages=%d",
            selected_model,
            max_tokens,
            len(messages),
        )

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"OpenRouter retornou HTTP {exc.response.status_code}: "
                    f"{exc.response.text[:500]}"
                ) from exc
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    f"Timeout na chamada ao OpenRouter após {_REQUEST_TIMEOUT}s"
                ) from exc
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Falha de conexão com OpenRouter: {exc}"
                ) from exc

        response_data: dict[str, Any] = response.json()

        logger.info(
            "OpenRouter response: model=%s tokens_in=%s tokens_out=%s",
            response_data.get("model", selected_model),
            response_data.get("usage", {}).get("prompt_tokens"),
            response_data.get("usage", {}).get("completion_tokens"),
        )

        return response_data

    def extract_content(self, response_data: dict[str, Any]) -> str:
        """Extrai o texto gerado da resposta da API.

        Args:
            response_data: Dicionário retornado por complete().

        Returns:
            Conteúdo textual gerado pelo modelo.

        Raises:
            RuntimeError: Se a resposta não contiver conteúdo válido.
        """
        content: Optional[str] = (
            response_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
        if not content:
            raise RuntimeError("OpenRouter retornou resposta vazia ou mal formatada.")
        return content.strip()

    def extract_usage(self, response_data: dict[str, Any]) -> tuple[int, int]:
        """Extrai contagem de tokens de entrada e saída.

        Args:
            response_data: Dicionário retornado por complete().

        Returns:
            Tupla (tokens_input, tokens_output).
        """
        usage: dict[str, Any] = response_data.get("usage", {})
        tokens_input: int = int(usage.get("prompt_tokens", 0))
        tokens_output: int = int(usage.get("completion_tokens", 0))
        return tokens_input, tokens_output

    def extract_model(self, response_data: dict[str, Any]) -> str:
        """Extrai o identificador do modelo efetivamente utilizado.

        Args:
            response_data: Dicionário retornado por complete().

        Returns:
            String com o ID do modelo (ex: 'openai/gpt-4o-mini').
        """
        return str(response_data.get("model", settings.OPENROUTER_MODEL))
