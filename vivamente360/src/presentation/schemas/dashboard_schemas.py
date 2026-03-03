"""Schemas Pydantic para o endpoint de dashboard.

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
