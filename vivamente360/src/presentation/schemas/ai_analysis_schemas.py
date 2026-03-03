"""Schemas Pydantic para o módulo de Análise por IA (Módulo 06).

Regra R1: Type hints completos em todos os campos.
Regra R4: PaginationMeta em todas as respostas de listagem.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Schemas de Request
# ---------------------------------------------------------------------------


class AiAnalysisRequest(BaseModel):
    """Payload para solicitar uma nova análise de IA.

    POST /ai-analyses/request
    """

    campaign_id: UUID = Field(description="UUID da campanha a analisar.")
    tipo: str = Field(
        description="Tipo de análise: 'sentimento', 'diagnostico' ou 'recomendacoes'."
    )
    setor_id: Optional[UUID] = Field(
        default=None,
        description="UUID do setor. Quando ausente, análise é para toda a campanha.",
    )
    dimensao: Optional[str] = Field(
        default=None,
        description=(
            "Dimensão HSE-IT específica para análise "
            "(ex: 'demandas', 'controle'). Quando ausente, analisa todas."
        ),
    )

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        allowed = {"sentimento", "diagnostico", "recomendacoes"}
        if v not in allowed:
            raise ValueError(
                f"tipo inválido: {v!r}. Valores aceitos: {sorted(allowed)}"
            )
        return v


# ---------------------------------------------------------------------------
# Schemas de Response
# ---------------------------------------------------------------------------


class AiAnalysisCreatedResponse(BaseModel):
    """Resposta imediata ao solicitar uma análise — antes do processamento."""

    analysis_id: UUID = Field(description="UUID da análise criada.")
    status: str = Field(
        default="pending",
        description="Status inicial da análise (sempre 'pending' na criação).",
    )
    message: str = Field(
        default=(
            "Análise enfileirada com sucesso. "
            "Use GET /ai-analyses/{analysis_id} para acompanhar o progresso."
        ),
        description="Mensagem informativa sobre como fazer polling.",
    )


class AiAnalysisResponse(BaseModel):
    """Resposta completa de uma análise de IA — usada no polling e na listagem."""

    id: UUID
    campaign_id: UUID
    setor_id: Optional[UUID]
    dimensao: Optional[str]
    tipo: str
    status: str
    model_usado: Optional[str]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    resultado: Optional[dict[str, Any]]
    erro: Optional[str]
    prompt_versao: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schemas de Listagem (Regra R4 — paginação obrigatória)
# ---------------------------------------------------------------------------


class AiAnalysisPaginationMeta(BaseModel):
    """Metadados de paginação para listagens de análises."""

    page: int
    page_size: int
    total: int
    pages: int


class AiAnalysisListResponse(BaseModel):
    """Resposta paginada da listagem de análises de uma campanha."""

    items: list[AiAnalysisResponse]
    pagination: AiAnalysisPaginationMeta


# ---------------------------------------------------------------------------
# Schemas de Resumo (GET /ai-analyses/{campaign_id}/summary)
# ---------------------------------------------------------------------------


class RecomendacaoPriorizada(BaseModel):
    """Recomendação extraída e priorizada a partir do resultado JSONB."""

    titulo: str
    prioridade: str
    prazo: str
    setor_id: Optional[UUID] = None
    setor_nome: Optional[str] = None
    analysis_id: UUID


class PorSetorSummary(BaseModel):
    """Resumo das análises concluídas agrupado por setor."""

    setor_id: Optional[UUID]
    total_analyses: int
    tipos_concluidos: list[str]
    ultimo_resultado: Optional[dict[str, Any]]
    ultimo_modelo: Optional[str]
    tokens_total: int


class AiAnalysisSummaryResponse(BaseModel):
    """Resposta do endpoint /summary — agrega análises concluídas da campanha."""

    campaign_id: UUID
    total_analyses: int
    total_completed: int
    total_pending: int
    total_failed: int
    tokens_input_total: int
    tokens_output_total: int
    por_setor: list[PorSetorSummary]
    recomendacoes_priorizadas: list[RecomendacaoPriorizada]
