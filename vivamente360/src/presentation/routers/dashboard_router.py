"""Router do dashboard — endpoint GET /dashboard/{campaign_id}.

Regra R3: TODOS os dados vêm de fact_score_dimensao.
Zero cálculos de score no request/response cycle.

Regra R4: Paginação obrigatória — o heatmap é paginado por dim_estrutura.
"""
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.analytics_repository import SQLAnalyticsRepository
from src.presentation.schemas.dashboard_schemas import (
    DashboardResponse,
    DashboardSummary,
    DimensaoScore,
    HeatmapCell,
    PaginationMeta,
)

router: APIRouter = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Limite máximo de itens por página (Regra R4)
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


def _build_analytics_repo(db: AsyncSession) -> SQLAnalyticsRepository:
    """Constrói SQLAnalyticsRepository com a sessão da request."""
    return SQLAnalyticsRepository(db)


@router.get(
    "/{campaign_id}",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard analítico da campanha",
    description=(
        "Retorna o dashboard completo de uma campanha: resumo executivo, "
        "scores por dimensão HSE-IT e heatmap setor×dimensão paginado. "
        "Todos os dados são lidos de fact_score_dimensao — zero cálculos em runtime. "
        "O heatmap é paginado pelo parâmetro page/page_size sobre dim_estrutura."
    ),
)
async def get_dashboard(
    campaign_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[
        int,
        Query(ge=1, description="Página do heatmap (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
    dimensao: Annotated[
        str | None,
        Query(description="Filtrar heatmap por dimensão HSE-IT específica."),
    ] = None,
    unidade_id: Annotated[
        UUID | None,
        Query(description="Filtrar por unidade organizacional."),
    ] = None,
    setor_id: Annotated[
        UUID | None,
        Query(description="Filtrar por setor."),
    ] = None,
) -> DashboardResponse:
    """Retorna o dashboard analítico pré-computado da campanha.

    Args:
        campaign_id: UUID da campanha a consultar.
        db: Sessão assíncrona do banco de dados.
        page: Página do heatmap (1-indexed, padrão 1).
        page_size: Quantidade de estruturas por página (máximo 100, padrão 20).
        dimensao: Filtro opcional por dimensão HSE-IT.
        unidade_id: Filtro opcional por unidade organizacional.
        setor_id: Filtro opcional por setor.

    Returns:
        DashboardResponse com summary, dimensoes, heatmap e pagination.
    """
    repo = _build_analytics_repo(db)

    # ------------------------------------------------------------------
    # 1. Summary — métricas globais da campanha
    # ------------------------------------------------------------------
    summary_data = await repo.get_dashboard_summary(campaign_id)

    summary = DashboardSummary(
        total_respostas=summary_data["total_respostas"],
        taxa_adesao=None,  # Calculado quando houver endpoint de convites
        indice_geral=summary_data["indice_geral"],
        nivel_geral=summary_data["nivel_geral"],
    )

    # ------------------------------------------------------------------
    # 2. Scores por dimensão — todos os 7 valores HSE-IT
    # ------------------------------------------------------------------
    dimensoes_data = await repo.get_dimensoes_scores(campaign_id)

    dimensoes = [
        DimensaoScore(
            dimensao=d["dimensao"],
            score_medio=d["score_medio"],
            nivel_risco=d["nivel_risco"],
            total_respostas=d["total_respostas"],
        )
        for d in dimensoes_data
    ]

    # ------------------------------------------------------------------
    # 3. Heatmap paginado — setor×dimensão
    # ------------------------------------------------------------------
    heatmap_data, total_estruturas = await repo.get_heatmap(
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
    )

    heatmap = [
        HeatmapCell(
            dim_estrutura_id=cell["dim_estrutura_id"],
            dimensao=cell["dimensao"],
            score_medio=cell["score_medio"],
            nivel_risco=cell["nivel_risco"],
            unidade_nome=cell.get("unidade_nome"),
            setor_nome=cell.get("setor_nome"),
            cargo_nome=cell.get("cargo_nome"),
        )
        for cell in heatmap_data
    ]

    total_pages = math.ceil(total_estruturas / page_size) if total_estruturas > 0 else 0

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total_estruturas,
        pages=total_pages,
    )

    return DashboardResponse(
        summary=summary,
        dimensoes=dimensoes,
        heatmap=heatmap,
        pagination=pagination,
    )
