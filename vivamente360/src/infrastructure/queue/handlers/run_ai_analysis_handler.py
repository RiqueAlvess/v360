"""Handler para tarefas do tipo 'run_ai_analysis'.

Payload esperado:
    {
        "analysis_id":  "<UUID do registro ai_analyses>",
        "campaign_id":  "<UUID da campanha>",
        "company_id":   "<UUID da empresa>",
        "setor_id":     "<UUID do setor | null>",
        "dimensao":     "<nome da dimensão HSE-IT | null>",
        "tipo":         "sentimento|diagnostico|recomendacoes"
    }

Pipeline:
    1. Validar payload e converter UUIDs.
    2. Verificar rate limit: máx. OPENROUTER_RATE_LIMIT_PER_HOUR análises/empresa/hora.
    3. Marcar analysis como 'processing'.
    4. Buscar textos livres criptografados das survey_responses da campanha/setor.
    5. Decriptografar em memória (LGPD — plaintext nunca persiste).
    6. Selecionar prompt template pelo tipo de análise.
    7. Montar scores HSE-IT do setor (quando disponíveis).
    8. Chamar OpenRouter via OpenRouterAdapter.
    9. Parsear e validar JSON retornado via Pydantic.
    10. Persistir resultado em ai_analyses.resultado (JSONB).
    11. Descartar plaintexts da memória.

Regra LGPD: Textos descriptografados existem APENAS em memória durante
a chamada à IA e são descartados imediatamente após o uso.

Regra inviolável: NUNCA chamado diretamente de um request HTTP.
Toda execução ocorre via task_queue → TaskWorker.
"""
import json
import logging
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.openrouter_adapter import OpenRouterAdapter
from src.infrastructure.ai.prompts import diagnostico_setor, recomendacoes, sentimento
from src.infrastructure.database.models.ai_analysis import AiAnalysis
from src.infrastructure.database.models.fact_score_dimensao import FactScoreDimensao
from src.infrastructure.database.models.sector import Sector
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.repositories.ai_analysis_repository import (
    SQLAiAnalysisRepository,
)
from src.shared.config import settings
from src.shared.security import decrypt_data

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload para esta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"analysis_id", "campaign_id", "company_id", "tipo"}
)

# Tipos de análise aceitos
_VALID_TIPOS: frozenset[str] = frozenset({"sentimento", "diagnostico", "recomendacoes"})

# Máximo de depoimentos a incluir no prompt (evita context overflow)
_MAX_DEPOIMENTOS: int = 50

# Tamanho máximo de cada depoimento no prompt (truncado se necessário)
_MAX_DEPOIMENTO_CHARS: int = 500


# ---------------------------------------------------------------------------
# Schemas Pydantic para validação do output da IA
# ---------------------------------------------------------------------------


class RecomendacaoSchema(BaseModel):
    """Schema para uma recomendação de ação retornada pela IA."""

    titulo: str
    prioridade: str
    prazo: str

    @field_validator("prioridade")
    @classmethod
    def validate_prioridade(cls, v: str) -> str:
        if v not in {"alta", "media", "baixa"}:
            raise ValueError(f"prioridade inválida: {v!r}")
        return v

    @field_validator("prazo")
    @classmethod
    def validate_prazo(cls, v: str) -> str:
        if v not in {"imediato", "30d", "90d"}:
            raise ValueError(f"prazo inválido: {v!r}")
        return v


class DiagnosticoResultadoSchema(BaseModel):
    """Schema de validação para output do prompt de diagnóstico."""

    resumo_executivo: str
    principais_temas: list[str]
    dimensoes_criticas: list[str]
    recomendacoes: list[RecomendacaoSchema]
    alertas_lgpd: list[str]

    @field_validator("alertas_lgpd")
    @classmethod
    def validate_lgpd_vazio(cls, v: list[str]) -> list[str]:
        """Garante que alertas_lgpd está sempre vazio — nenhum dado identificável."""
        return []


class SentimentoResultadoSchema(BaseModel):
    """Schema de validação para output do prompt de sentimento agregado."""

    sentimento_geral: str
    score_medio: float
    distribuicao: dict[str, int]
    temas_negativos_recorrentes: list[str]
    temas_positivos_recorrentes: list[str]
    alertas_lgpd: list[str]

    @field_validator("sentimento_geral")
    @classmethod
    def validate_sentimento_geral(cls, v: str) -> str:
        if v not in {"positivo", "neutro", "negativo", "critico"}:
            raise ValueError(f"sentimento_geral inválido: {v!r}")
        return v

    @field_validator("alertas_lgpd")
    @classmethod
    def validate_lgpd_vazio(cls, v: list[str]) -> list[str]:
        return []


class RecomendacaoDetalhadaSchema(BaseModel):
    """Schema para recomendação detalhada com campos extras."""

    titulo: str
    descricao: str
    prioridade: str
    prazo: str
    dimensao_alvo: Optional[str] = None
    responsavel_sugerido: Optional[str] = None

    @field_validator("prioridade")
    @classmethod
    def validate_prioridade(cls, v: str) -> str:
        if v not in {"alta", "media", "baixa"}:
            raise ValueError(f"prioridade inválida: {v!r}")
        return v

    @field_validator("prazo")
    @classmethod
    def validate_prazo(cls, v: str) -> str:
        if v not in {"imediato", "30d", "90d"}:
            raise ValueError(f"prazo inválido: {v!r}")
        return v


class RecomendacoesResultadoSchema(BaseModel):
    """Schema de validação para output do prompt de recomendações."""

    recomendacoes: list[RecomendacaoDetalhadaSchema]
    alertas_lgpd: list[str]

    @field_validator("alertas_lgpd")
    @classmethod
    def validate_lgpd_vazio(cls, v: list[str]) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Handler principal
# ---------------------------------------------------------------------------


class RunAiAnalysisHandler(BaseTaskHandler):
    """Processa análise de IA via OpenRouter para um setor/campanha.

    Orquestra o ciclo completo: busca de dados, decriptografia em memória,
    chamada à IA, validação do resultado e persistência no banco.

    Rate limit: máximo OPENROUTER_RATE_LIMIT_PER_HOUR análises por empresa/hora.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._adapter = OpenRouterAdapter()

    async def execute(self, payload: dict[str, Any]) -> None:
        """Executa a análise de IA completa.

        Args:
            payload: Dicionário com analysis_id, campaign_id, company_id,
                     setor_id (opcional), dimensao (opcional) e tipo.

        Raises:
            ValueError: Se o payload for inválido, UUID mal formatado,
                        tipo desconhecido ou rate limit excedido.
            RuntimeError: Se a análise não for encontrada, a chamada à IA
                         falhar ou o resultado for inválido.
        """
        self._validate_payload(payload)

        analysis_id: UUID = self._parse_uuid(payload["analysis_id"], "analysis_id")
        campaign_id: UUID = self._parse_uuid(payload["campaign_id"], "campaign_id")
        company_id: UUID = self._parse_uuid(payload["company_id"], "company_id")
        tipo: str = payload["tipo"]

        setor_id: Optional[UUID] = None
        if payload.get("setor_id"):
            setor_id = self._parse_uuid(payload["setor_id"], "setor_id")

        dimensao: Optional[str] = payload.get("dimensao")

        logger.info(
            "Iniciando análise de IA: analysis_id=%s tipo=%s setor_id=%s",
            analysis_id,
            tipo,
            setor_id,
        )

        repo = SQLAiAnalysisRepository(self._db)

        # -------------------------------------------------------------------
        # 1. Verificar rate limit por empresa
        # -------------------------------------------------------------------
        count_last_hour: int = await repo.count_by_company_last_hour(company_id)
        if count_last_hour >= settings.OPENROUTER_RATE_LIMIT_PER_HOUR:
            raise ValueError(
                f"Rate limit excedido: empresa {company_id} atingiu "
                f"{settings.OPENROUTER_RATE_LIMIT_PER_HOUR} análises/hora. "
                f"Atual: {count_last_hour}."
            )

        # -------------------------------------------------------------------
        # 2. Buscar e validar o registro AiAnalysis
        # -------------------------------------------------------------------
        analysis: Optional[AiAnalysis] = await repo.get_by_id(analysis_id)
        if analysis is None:
            raise RuntimeError(
                f"AiAnalysis não encontrada: analysis_id={analysis_id}"
            )

        # -------------------------------------------------------------------
        # 3. Marcar como 'processing'
        # -------------------------------------------------------------------
        await repo.update_status(analysis_id, "processing")
        await self._db.commit()

        # -------------------------------------------------------------------
        # 4. Coletar nome do setor (para o prompt)
        # -------------------------------------------------------------------
        setor_nome: str = await self._get_setor_nome(setor_id)

        # -------------------------------------------------------------------
        # 5. Buscar textos livres criptografados
        # -------------------------------------------------------------------
        textos_criptografados: list[str] = await self._fetch_textos_livres(
            campaign_id=campaign_id,
            setor_id=setor_id,
        )

        # -------------------------------------------------------------------
        # 6. Decriptografar em memória (LGPD)
        # -------------------------------------------------------------------
        textos_plaintext: list[str] = self._decrypt_textos(textos_criptografados)

        # Liberar referências à lista criptografada
        del textos_criptografados

        if not textos_plaintext:
            logger.warning(
                "Nenhum texto livre disponível para análise: "
                "analysis_id=%s campaign_id=%s setor_id=%s",
                analysis_id,
                campaign_id,
                setor_id,
            )
            await repo.update_status(
                analysis_id,
                "failed",
                erro="Nenhum texto livre disponível para análise neste setor/campanha.",
            )
            await self._db.commit()
            return

        # -------------------------------------------------------------------
        # 7. Buscar scores HSE-IT para contextualização do prompt
        # -------------------------------------------------------------------
        scores_texto: str = await self._get_scores_texto(campaign_id, setor_id)

        # -------------------------------------------------------------------
        # 8. Montar mensagens do prompt e chamar OpenRouter
        # -------------------------------------------------------------------
        messages, prompt_versao, max_tokens, temperature = self._build_messages(
            tipo=tipo,
            setor_nome=setor_nome,
            textos=textos_plaintext,
            scores_texto=scores_texto,
            dimensao=dimensao,
        )

        # Descartar plaintexts após montar o prompt
        del textos_plaintext

        response_data: dict[str, Any] = await self._adapter.complete(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # -------------------------------------------------------------------
        # 9. Extrair conteúdo e tokens
        # -------------------------------------------------------------------
        raw_content: str = self._adapter.extract_content(response_data)
        tokens_input, tokens_output = self._adapter.extract_usage(response_data)
        model_usado: str = self._adapter.extract_model(response_data)

        # -------------------------------------------------------------------
        # 10. Parsear e validar JSON retornado
        # -------------------------------------------------------------------
        resultado: dict[str, Any] = self._parse_and_validate(raw_content, tipo)

        # -------------------------------------------------------------------
        # 11. Persistir resultado
        # -------------------------------------------------------------------
        await repo.update_resultado(
            analysis_id=analysis_id,
            resultado=resultado,
            model_usado=model_usado,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            prompt_versao=prompt_versao,
        )
        await self._db.commit()

        logger.info(
            "Análise de IA concluída: analysis_id=%s tipo=%s "
            "tokens_in=%d tokens_out=%d model=%s",
            analysis_id,
            tipo,
            tokens_input,
            tokens_output,
            model_usado,
        )

    # -----------------------------------------------------------------------
    # Métodos privados de suporte
    # -----------------------------------------------------------------------

    async def _get_setor_nome(self, setor_id: Optional[UUID]) -> str:
        """Retorna o nome do setor ou 'Geral' para análises sem recorte."""
        if setor_id is None:
            return "Geral"

        result = await self._db.execute(
            select(Sector.nome).where(Sector.id == setor_id)
        )
        nome: Optional[str] = result.scalar_one_or_none()
        return nome or "Setor desconhecido"

    async def _fetch_textos_livres(
        self,
        campaign_id: UUID,
        setor_id: Optional[UUID],
    ) -> list[str]:
        """Busca textos livres criptografados das survey_responses.

        Filtra por setor quando setor_id é informado.
        Limita ao máximo de _MAX_DEPOIMENTOS para evitar overflow de contexto.
        """
        from src.infrastructure.database.models.invitation import Invitation

        # Busca responses com texto_livre não nulo para a campanha
        stmt = (
            select(SurveyResponse.texto_livre)
            .where(
                SurveyResponse.campaign_id == campaign_id,
                SurveyResponse.texto_livre.isnot(None),
            )
            .limit(_MAX_DEPOIMENTOS)
        )

        result = await self._db.execute(stmt)
        rows: list[Optional[str]] = list(result.scalars().all())
        return [r for r in rows if r]

    def _decrypt_textos(self, textos_criptografados: list[str]) -> list[str]:
        """Decriptografa textos em memória — plaintext nunca persiste (LGPD)."""
        plaintexts: list[str] = []
        for texto_enc in textos_criptografados:
            try:
                plain: str = decrypt_data(texto_enc, settings.ENCRYPTION_KEY)
                plaintexts.append(plain[:_MAX_DEPOIMENTO_CHARS])
            except (ValueError, Exception) as exc:
                logger.warning("Falha ao decriptografar texto_livre: %s", exc)
                continue
        return plaintexts

    async def _get_scores_texto(
        self,
        campaign_id: UUID,
        setor_id: Optional[UUID],
    ) -> str:
        """Monta string formatada com scores HSE-IT do setor para o prompt."""
        stmt = select(
            FactScoreDimensao.dimensao,
            FactScoreDimensao.score_medio,
            FactScoreDimensao.nivel_risco,
        ).where(
            FactScoreDimensao.campaign_id == campaign_id,
        )

        result = await self._db.execute(stmt)
        rows = result.all()

        if not rows:
            return "Scores HSE-IT ainda não calculados para esta campanha."

        linhas: list[str] = []
        for row in rows:
            dimensao_val = row.dimensao.value if hasattr(row.dimensao, "value") else row.dimensao
            nivel_val = row.nivel_risco.value if hasattr(row.nivel_risco, "value") else row.nivel_risco
            score_val = float(row.score_medio) if row.score_medio else 0.0
            linhas.append(
                f"- {dimensao_val}: {score_val:.2f}/5.00 (risco: {nivel_val})"
            )

        return "\n".join(linhas)

    def _build_messages(
        self,
        tipo: str,
        setor_nome: str,
        textos: list[str],
        scores_texto: str,
        dimensao: Optional[str],
    ) -> tuple[list[dict[str, str]], str, int, float]:
        """Monta as mensagens do prompt e retorna metadados de configuração.

        Returns:
            Tupla (messages, prompt_versao, max_tokens, temperature).
        """
        # Formata depoimentos numerados para o prompt
        depoimentos_formatados: str = "\n".join(
            f"{i + 1}. {texto}" for i, texto in enumerate(textos)
        )

        if tipo == "diagnostico":
            system_msg = diagnostico_setor.PROMPT_DIAGNOSTICO_SYSTEM
            user_msg = diagnostico_setor.PROMPT_DIAGNOSTICO_USER.format(
                total=len(textos),
                setor_nome=setor_nome,
                depoimentos=depoimentos_formatados,
                scores_dimensoes=scores_texto,
            )
            return (
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                diagnostico_setor.PROMPT_VERSION,
                diagnostico_setor.MAX_TOKENS,
                diagnostico_setor.TEMPERATURE,
            )

        elif tipo == "sentimento":
            system_msg = sentimento.PROMPT_SENTIMENTO_SYSTEM
            user_msg = sentimento.PROMPT_SENTIMENTO_USER.format(
                total=len(textos),
                setor_nome=setor_nome,
                depoimentos=depoimentos_formatados,
            )
            return (
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                sentimento.PROMPT_VERSION,
                sentimento.MAX_TOKENS,
                sentimento.TEMPERATURE,
            )

        else:  # recomendacoes
            system_msg = recomendacoes.PROMPT_RECOMENDACOES_SYSTEM
            user_msg = recomendacoes.PROMPT_RECOMENDACOES_USER.format(
                setor_nome=setor_nome,
                scores_dimensoes=scores_texto,
                resumo_diagnostico=(
                    "Análise baseada nos depoimentos coletados. "
                    "Foque nas dimensões com maior risco identificado."
                ),
                dimensao_foco=dimensao or "Todas as dimensões HSE-IT",
            )
            return (
                [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                recomendacoes.PROMPT_VERSION,
                recomendacoes.MAX_TOKENS,
                recomendacoes.TEMPERATURE,
            )

    def _parse_and_validate(
        self,
        raw_content: str,
        tipo: str,
    ) -> dict[str, Any]:
        """Parseia o JSON retornado pela IA e valida com o schema Pydantic correto.

        Args:
            raw_content: String JSON retornada pelo LLM.
            tipo: Tipo da análise para selecionar o schema de validação.

        Returns:
            Dicionário validado e serializado pelo schema Pydantic.

        Raises:
            RuntimeError: Se o JSON for inválido ou os campos não passarem na validação.
        """
        try:
            parsed: dict[str, Any] = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"IA retornou JSON inválido: {raw_content[:300]!r}"
            ) from exc

        try:
            if tipo == "diagnostico":
                validated = DiagnosticoResultadoSchema.model_validate(parsed)
            elif tipo == "sentimento":
                validated = SentimentoResultadoSchema.model_validate(parsed)
            else:  # recomendacoes
                validated = RecomendacoesResultadoSchema.model_validate(parsed)
        except Exception as exc:
            raise RuntimeError(
                f"Resultado da IA não passou na validação Pydantic "
                f"(tipo={tipo!r}): {exc}"
            ) from exc

        return validated.model_dump()

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Verifica que todos os campos obrigatórios estão presentes e tipo é válido."""
        missing = _REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Payload inválido para run_ai_analysis. "
                f"Campos ausentes: {sorted(missing)}"
            )

        tipo: str = payload.get("tipo", "")
        if tipo not in _VALID_TIPOS:
            raise ValueError(
                f"Tipo de análise inválido: {tipo!r}. "
                f"Aceitos: {sorted(_VALID_TIPOS)}"
            )

    def _parse_uuid(self, value: str, field_name: str) -> UUID:
        """Converte string em UUID com mensagem de erro clara."""
        try:
            return UUID(str(value))
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Campo '{field_name}' não é um UUID válido: {value!r}"
            ) from exc
