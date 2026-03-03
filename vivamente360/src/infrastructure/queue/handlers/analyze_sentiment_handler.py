"""Handler para tarefas do tipo 'analyze_sentiment'.

Payload esperado:
    {
        "survey_response_id": "<UUID da survey_response>",
        "campaign_id": "<UUID da campanha>"
    }

Pipeline:
    1. Buscar survey_response pelo ID.
    2. Verificar que texto_livre não é None (criptografado em repouso).
    3. Decriptografar texto_livre em memória (AES-256-GCM).
    4. Chamar OpenRouter com o texto descriptografado.
    5. Parsear a resposta da IA: classificação + score numérico.
    6. Atualizar survey_response.sentimento e survey_response.sentimento_score.
    7. Descartar o plaintext — jamais persistir em texto claro.

Regra LGPD: O texto descriptografado existe APENAS em memória durante a
chamada à IA e é descartado imediatamente após o uso.
"""
import json
import logging
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.sentimento_type import SentimentoType
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.shared.config import settings
from src.shared.security import decrypt_data

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset({"survey_response_id", "campaign_id"})

# Intervalo válido para sentimento_score
_SCORE_MIN: Decimal = Decimal("-1.0")
_SCORE_MAX: Decimal = Decimal("1.0")

# Prompt de sistema para a análise de sentimento
_SYSTEM_PROMPT: str = (
    "Você é um especialista em saúde psicossocial do trabalho. "
    "Analise o texto fornecido por um colaborador sobre como está se sentindo na empresa. "
    "Responda APENAS com um JSON válido contendo dois campos:\n"
    '  "classificacao": uma das opções: "positivo", "neutro", "negativo" ou "critico"\n'
    '  "score": número decimal entre -1.0 e 1.0, onde:\n'
    "    +1.0 = muito positivo, bem-estar elevado\n"
    "     0.0 = neutro\n"
    "    -0.5 = negativo moderado\n"
    "    -1.0 = crítico, sofrimento intenso\n"
    "Não inclua explicações, apenas o JSON."
)


class AnalyzeSentimentHandler(BaseTaskHandler):
    """Analisa o sentimento do texto livre de uma survey_response via LLM.

    Chama a API OpenRouter de forma assíncrona, parseia a resposta e persiste
    a classificação qualitativa (sentimento) e o score numérico (sentimento_score)
    diretamente no registro survey_response.

    O texto em plaintext é decriptografado apenas em memória e descartado após uso.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Executa a análise de sentimento do texto livre.

        Args:
            payload: Dicionário com survey_response_id e campaign_id.

        Raises:
            ValueError: Se o payload estiver incompleto, o UUID for inválido ou
                        survey_response não tiver texto_livre.
            RuntimeError: Se a survey_response não for encontrada no banco ou
                         a chamada à API OpenRouter falhar.
        """
        self._validate_payload(payload)
        response_id: UUID = self._parse_uuid(payload["survey_response_id"], "survey_response_id")

        logger.info("Iniciando análise de sentimento: survey_response_id=%s", response_id)

        # ---------------------------------------------------------------
        # 1. Buscar survey_response no banco
        # ---------------------------------------------------------------
        result = await self._db.execute(
            select(SurveyResponse).where(SurveyResponse.id == response_id)
        )
        survey_response = result.scalar_one_or_none()

        if survey_response is None:
            raise RuntimeError(
                f"SurveyResponse não encontrada: survey_response_id={response_id}"
            )

        if not survey_response.texto_livre:
            logger.warning(
                "SurveyResponse sem texto_livre — tarefa ignorada: id=%s", response_id
            )
            return

        # ---------------------------------------------------------------
        # 2. Decriptografar texto_livre apenas em memória (LGPD)
        # ---------------------------------------------------------------
        try:
            texto_plaintext: str = decrypt_data(
                survey_response.texto_livre,
                settings.ENCRYPTION_KEY,
            )
        except ValueError as exc:
            raise RuntimeError(
                f"Falha ao decriptografar texto_livre: survey_response_id={response_id}"
            ) from exc

        # ---------------------------------------------------------------
        # 3. Chamar OpenRouter para análise de sentimento
        # ---------------------------------------------------------------
        classificacao, score = await self._call_openrouter(texto_plaintext)

        # Descartar plaintext — não deve sobreviver além deste ponto
        del texto_plaintext

        # ---------------------------------------------------------------
        # 4. Persistir sentimento e sentimento_score na survey_response
        # ---------------------------------------------------------------
        await self._db.execute(
            update(SurveyResponse)
            .where(SurveyResponse.id == response_id)
            .values(
                sentimento=classificacao,
                sentimento_score=score,
            )
        )
        await self._db.commit()

        logger.info(
            "Sentimento analisado e persistido: survey_response_id=%s "
            "classificacao=%s score=%s",
            response_id,
            classificacao.value,
            score,
        )

    async def _call_openrouter(
        self, texto: str
    ) -> tuple[SentimentoType, Decimal]:
        """Chama a API OpenRouter e parseia a classificação de sentimento.

        Args:
            texto: Texto plaintext do respondente (apenas em memória).

        Returns:
            Tupla (SentimentoType, Decimal) com classificação e score numérico.

        Raises:
            RuntimeError: Se a chamada HTTP falhar ou a resposta for inválida.
        """
        request_body: dict[str, Any] = {
            "model": settings.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": texto},
            ],
            "temperature": 0.1,
            "max_tokens": 100,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://vivamente.com.br",
                        "X-Title": "VIVAMENTE 360",
                    },
                    json=request_body,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"OpenRouter retornou HTTP {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise RuntimeError(
                    f"Falha de conexão com OpenRouter: {exc}"
                ) from exc

        response_data: dict[str, Any] = response.json()
        raw_content: Optional[str] = (
            response_data.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

        if not raw_content:
            raise RuntimeError("OpenRouter retornou resposta vazia ou mal formatada.")

        return self._parse_sentiment_response(raw_content)

    def _parse_sentiment_response(
        self, raw_content: str
    ) -> tuple[SentimentoType, Decimal]:
        """Parseia o JSON retornado pela IA para (SentimentoType, Decimal).

        Args:
            raw_content: String JSON retornada pelo LLM.

        Returns:
            Tupla (SentimentoType, Decimal) com classificação e score.

        Raises:
            RuntimeError: Se o JSON for inválido ou os valores forem inesperados.
        """
        try:
            parsed: dict[str, Any] = json.loads(raw_content.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"IA retornou JSON inválido: {raw_content!r}"
            ) from exc

        raw_classificacao: str = str(parsed.get("classificacao", "")).strip().lower()
        raw_score: Any = parsed.get("score", 0.0)

        try:
            classificacao = SentimentoType(raw_classificacao)
        except ValueError as exc:
            raise RuntimeError(
                f"Classificação de sentimento inválida: {raw_classificacao!r}. "
                f"Valores aceitos: {[e.value for e in SentimentoType]}"
            ) from exc

        try:
            score = Decimal(str(raw_score)).quantize(Decimal("0.001"))
        except Exception as exc:
            raise RuntimeError(
                f"Score de sentimento inválido: {raw_score!r}"
            ) from exc

        # Clamp para garantir o intervalo [-1.0, +1.0]
        score = max(_SCORE_MIN, min(_SCORE_MAX, score))

        return classificacao, score

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Verifica que todos os campos obrigatórios estão presentes.

        Args:
            payload: Payload recebido da tarefa.

        Raises:
            ValueError: Se algum campo obrigatório estiver ausente.
        """
        missing = _REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Payload inválido para analyze_sentiment. "
                f"Campos ausentes: {sorted(missing)}"
            )

    def _parse_uuid(self, value: str, field_name: str) -> UUID:
        """Converte string em UUID com mensagem de erro clara.

        Args:
            value: String a converter.
            field_name: Nome do campo para mensagem de erro.

        Returns:
            UUID convertido.

        Raises:
            ValueError: Se o valor não for um UUID válido.
        """
        try:
            return UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Campo '{field_name}' não é um UUID válido: {value!r}"
            ) from exc
