"""Schemas Pydantic para os endpoints de dashboard — Módulos 06 e 09.

Módulo 06: DashboardResponse (campanha única, summary + heatmap paginado).
Módulo 09: HeatmapResponse, TopRiskItem, CampaignDimensaoScore, DeltaDimensao,
           CompareResponse, TrendPoint, TrendsResponse.

Todos os campos de score são lidos de fact_score_dimensao — zero cálculo aqui.
Regra R4: paginação obrigatória em todos os endpoints de listagem.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PaginationMeta(BaseModel):
    """Metadados de paginação para endpoints de listagem (Regra R4)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    page: int = Field(..., ge=1, description="Página atual (1-indexed).")
    page_size: int = Field(..., ge=1, le=100, description="Itens por página (máximo 100).")
    total: int = Field(..., ge=0, description="Total de itens disponíveis.")
    pages: int = Field(..., ge=0, description="Total de páginas.")


class DashboardSummary(BaseModel):
    """Resumo executivo da campanha — todos os valores pré-computados."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total_respostas: int = Field(
        ..., ge=0, description="Total de respostas processadas na campanha."
    )
    taxa_adesao: Optional[float] = Field(
        None,
        description="Percentual de respondentes em relação a convidados. "
        "None quando não há convites registrados.",
    )
    indice_geral: float = Field(
        ..., description="Score médio geral da campanha (1.0 a 5.0)."
    )
    nivel_geral: str = Field(
        ..., description="Nível de risco geral: aceitavel, moderado, importante ou critico."
    )


class DimensaoScore(BaseModel):
    """Score pré-computado de uma dimensão HSE-IT."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dimensao: str = Field(..., description="Identificador da dimensão HSE-IT.")
    score_medio: float = Field(..., description="Score médio da dimensão (1.0 a 5.0).")
    nivel_risco: str = Field(
        ..., description="Nível de risco: aceitavel, moderado, importante ou critico."
    )
    total_respostas: int = Field(
        ..., ge=0, description="Número de respostas que compõem o score."
    )


class HeatmapCell(BaseModel):
    """Célula do heatmap setor×dimensão com score pré-computado."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dim_estrutura_id: str = Field(..., description="UUID da dimensão estrutural.")
    dimensao: str = Field(..., description="Identificador da dimensão HSE-IT.")
    score_medio: float = Field(..., description="Score médio da célula (1.0 a 5.0).")
    nivel_risco: str = Field(
        ..., description="Nível de risco: aceitavel, moderado, importante ou critico."
    )
    unidade_nome: Optional[str] = Field(
        None, description="Nome da unidade organizacional (snapshot)."
    )
    setor_nome: Optional[str] = Field(
        None, description="Nome do setor (snapshot)."
    )
    cargo_nome: Optional[str] = Field(
        None, description="Nome do cargo (snapshot)."
    )


class DashboardResponse(BaseModel):
    """Resposta completa do endpoint GET /dashboard/{campaign_id}.

    Todos os dados são lidos de fact_score_dimensao.
    Zero cálculos no request/response cycle (Regra R3).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    summary: DashboardSummary = Field(..., description="Resumo executivo da campanha.")
    dimensoes: list[DimensaoScore] = Field(
        ..., description="Score e nível de risco para cada uma das 7 dimensões HSE-IT."
    )
    heatmap: list[HeatmapCell] = Field(
        ..., description="Matriz setor×dimensão com scores paginados."
    )
    pagination: PaginationMeta = Field(
        ..., description="Metadados de paginação do heatmap."
    )


# ---------------------------------------------------------------------------
# Módulo 09 — Schemas adicionais para filtros, comparativo e tendências
# ---------------------------------------------------------------------------


class HeatmapResponse(BaseModel):
    """Resposta do endpoint GET /dashboard/{campaign_id}/heatmap.

    Endpoint dedicado ao heatmap com suporte a filtros opcionais por
    unidade, setor e dimensão (Módulo 09).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    cells: list[HeatmapCell] = Field(
        ..., description="Células do heatmap setor×dimensão paginadas."
    )
    pagination: PaginationMeta = Field(
        ..., description="Metadados de paginação por dim_estrutura."
    )


class TopRiskItem(BaseModel):
    """Item do ranking de maior risco — combinação setor+dimensão."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dim_estrutura_id: str = Field(..., description="UUID da dimensão estrutural.")
    dimensao: str = Field(..., description="Dimensão HSE-IT com maior risco.")
    score_medio: float = Field(..., description="Score médio da célula (1.0 a 5.0).")
    nivel_risco: str = Field(
        ..., description="Nível de risco: aceitavel, moderado, importante ou critico."
    )
    unidade_nome: Optional[str] = Field(
        None, description="Nome da unidade organizacional (snapshot)."
    )
    setor_nome: Optional[str] = Field(
        None, description="Nome do setor (snapshot)."
    )
    cargo_nome: Optional[str] = Field(
        None, description="Nome do cargo (snapshot)."
    )


class TopRisksResponse(BaseModel):
    """Resposta do endpoint GET /dashboard/{campaign_id}/top-risks."""

    model_config = ConfigDict(str_strip_whitespace=True)

    top_risks: list[TopRiskItem] = Field(
        ..., description="Top 5 combinações setor+dimensão com maior risco (score mínimo)."
    )


class CampaignDimensaoScore(BaseModel):
    """Score de uma dimensão específica em uma campanha específica."""

    model_config = ConfigDict(str_strip_whitespace=True)

    campaign_id: str = Field(..., description="UUID da campanha.")
    campaign_nome: str = Field(..., description="Nome da campanha.")
    dimensao: str = Field(..., description="Identificador da dimensão HSE-IT.")
    score_campanha: float = Field(..., description="Score médio da dimensão na campanha.")
    nivel_risco: str = Field(
        ..., description="Nível de risco: aceitavel, moderado, importante ou critico."
    )
    total_setores: int = Field(
        ..., ge=0, description="Quantidade de setores distintos com dados."
    )


class ScorePorCampanha(BaseModel):
    """Score de uma campanha em uma dimensão específica — usado no delta."""

    model_config = ConfigDict(str_strip_whitespace=True)

    campaign_id: str = Field(..., description="UUID da campanha.")
    campaign_nome: str = Field(..., description="Nome da campanha.")
    score_campanha: float = Field(..., description="Score médio da dimensão.")
    nivel_risco: str = Field(..., description="Nível de risco classificado.")


class DeltaDimensao(BaseModel):
    """Delta de uma dimensão HSE-IT entre as campanhas comparadas."""

    model_config = ConfigDict(str_strip_whitespace=True)

    dimensao: str = Field(..., description="Identificador da dimensão HSE-IT.")
    scores_por_campanha: list[ScorePorCampanha] = Field(
        ..., description="Score de cada campanha nesta dimensão."
    )
    variacao_percentual: float = Field(
        ...,
        description="Variação percentual entre o maior e o menor score "
        "[(max - min) / min * 100]. Quanto maior, mais divergente a dimensão.",
    )


class CompareResponse(BaseModel):
    """Resposta do endpoint GET /dashboard/compare."""

    model_config = ConfigDict(str_strip_whitespace=True)

    campaigns: list[CampaignDimensaoScore] = Field(
        ..., description="Scores de todas as campanhas comparadas por dimensão."
    )
    delta_por_dimensao: list[DeltaDimensao] = Field(
        ...,
        description="Variação percentual por dimensão entre as campanhas, "
        "ordenado do mais divergente para o menos divergente.",
    )


class TrendPoint(BaseModel):
    """Ponto de tendência temporal de uma campanha."""

    model_config = ConfigDict(str_strip_whitespace=True)

    campaign_id: str = Field(..., description="UUID da campanha.")
    campaign_nome: str = Field(..., description="Nome da campanha.")
    data_inicio: str = Field(..., description="Data de início da campanha (ISO 8601).")
    score_geral: float = Field(
        ..., description="Score médio geral da campanha (1.0 a 5.0)."
    )
    nivel_geral: str = Field(
        ..., description="Nível de risco geral: aceitavel, moderado, importante ou critico."
    )


class TrendsResponse(BaseModel):
    """Resposta do endpoint GET /dashboard/trends/{company_id}."""

    model_config = ConfigDict(str_strip_whitespace=True)

    tendencias: list[TrendPoint] = Field(
        ...,
        description="Evolução temporal do score geral por campanha, "
        "ordenada por data_inicio ASC. Usada para gráfico de linha.",
    )
