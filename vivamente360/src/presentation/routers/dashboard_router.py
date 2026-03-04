"""Router do dashboard — Módulos 06 e 09.

Módulo 06: GET /dashboard/{campaign_id}
    Dashboard completo com summary, scores por dimensão e heatmap paginado.

Módulo 09: Filtros avançados, comparativo e tendências
    GET /dashboard/compare                   — comparativo entre campanhas
    GET /dashboard/trends/{company_id}       — evolução temporal por empresa
    GET /dashboard/{campaign_id}/heatmap     — heatmap com filtros dedicados
    GET /dashboard/{campaign_id}/top-risks   — top 5 combinações de maior risco

IMPORTANTE: rotas fixas (/compare, /trends/{id}) são declaradas ANTES de
/{campaign_id} para evitar captura pelo parâmetro variável de caminho.

Regra R3: TODOS os dados vêm de fact_score_dimensao — zero cálculos em runtime.
Regra R4: Paginação obrigatória em todos os endpoints de listagem.
"""
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.dashboard_repository import SQLDashboardRepository
from src.presentation.schemas.dashboard_schemas import (
    CompareResponse,
    CampaignDimensaoScore,
    DashboardResponse,
    DashboardSummary,
    DeltaDimensao,
    DimensaoScore,
    HeatmapCell,
    HeatmapResponse,
    PaginationMeta,
    ScorePorCampanha,
    TopRiskItem,
    TopRisksResponse,
    TrendPoint,
    TrendsResponse,
)

router: APIRouter = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Limite máximo de itens por página (Regra R4)
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20
# Máximo de campanhas no comparativo
_MAX_CAMPANHAS_COMPARE: int = 3


def _build_dashboard_repo(db: AsyncSession) -> SQLDashboardRepository:
    """Constrói SQLDashboardRepository com a sessão da request."""
    return SQLDashboardRepository(db)


# ===========================================================================
# Módulo 09 — Rotas fixas declaradas ANTES de /{campaign_id}
# ===========================================================================


@router.get(
    "/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Comparativo entre campanhas por dimensão",
    description=(
        "Compara até 3 campanhas retornando scores por dimensão e o delta percentual "
        "entre elas. Aceita filtros opcionais por dimensão e unidade organizacional. "
        "Todos os dados vêm de fact_score_dimensao — zero cálculos em runtime (Regra R3)."
    ),
)
async def get_compare(
    db: Annotated[AsyncSession, Depends(get_db)],
    campaign_ids: Annotated[
        str,
        Query(
            description="UUIDs das campanhas separados por vírgula (máximo 3). "
            "Ex: ?campaign_ids=uuid1,uuid2,uuid3",
        ),
    ],
    dimensao: Annotated[
        str | None,
        Query(description="Filtrar por dimensão HSE-IT específica."),
    ] = None,
    unidade_id: Annotated[
        UUID | None,
        Query(description="Filtrar por unidade organizacional."),
    ] = None,
) -> CompareResponse:
    """Compara até 3 campanhas retornando scores e delta percentual por dimensão.

    Args:
        db: Sessão assíncrona do banco de dados.
        campaign_ids: UUIDs das campanhas separados por vírgula (máximo 3).
        dimensao: Filtro opcional por dimensão HSE-IT.
        unidade_id: Filtro opcional por unidade organizacional.

    Returns:
        CompareResponse com campaigns (scores por campanha+dimensão) e
        delta_por_dimensao (variação percentual entre campanhas).

    Raises:
        HTTPException 422: Se mais de 3 campaign_ids forem fornecidos.
        HTTPException 422: Se algum campaign_id não for um UUID válido.
    """
    # Parsear e validar lista de campaign_ids
    raw_ids = [cid.strip() for cid in campaign_ids.split(",") if cid.strip()]
    if not raw_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O parâmetro campaign_ids não pode estar vazio.",
        )
    if len(raw_ids) > _MAX_CAMPANHAS_COMPARE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Máximo de {_MAX_CAMPANHAS_COMPARE} campanhas por comparativo. "
            f"Recebido: {len(raw_ids)}.",
        )

    try:
        parsed_ids: list[UUID] = [UUID(cid) for cid in raw_ids]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Um ou mais campaign_ids não são UUIDs válidos.",
        )

    repo = _build_dashboard_repo(db)
    data = await repo.get_compare(
        campaign_ids=parsed_ids,
        dimensao=dimensao,
        unidade_id=unidade_id,
    )

    campaigns = [
        CampaignDimensaoScore(
            campaign_id=item["campaign_id"],
            campaign_nome=item["campaign_nome"],
            dimensao=item["dimensao"],
            score_campanha=item["score_campanha"],
            nivel_risco=item["nivel_risco"],
            total_setores=item["total_setores"],
        )
        for item in data["campaigns"]
    ]

    delta_por_dimensao = [
        DeltaDimensao(
            dimensao=delta["dimensao"],
            scores_por_campanha=[
                ScorePorCampanha(
                    campaign_id=s["campaign_id"],
                    campaign_nome=s["campaign_nome"],
                    score_campanha=s["score_campanha"],
                    nivel_risco=s["nivel_risco"],
                )
                for s in delta["scores_por_campanha"]
            ],
            variacao_percentual=delta["variacao_percentual"],
        )
        for delta in data["delta_por_dimensao"]
    ]

    return CompareResponse(campaigns=campaigns, delta_por_dimensao=delta_por_dimensao)


@router.get(
    "/trends/{company_id}",
    response_model=TrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Evolução temporal do score geral por empresa",
    description=(
        "Retorna a série temporal de scores gerais de todas as campanhas de uma empresa, "
        "ordenada por data_inicio. Usada para o gráfico de linha no relatório executivo. "
        "Todos os dados vêm de fact_score_dimensao (Regra R3)."
    ),
)
async def get_trends(
    company_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrendsResponse:
    """Retorna a evolução temporal do score geral por campanha da empresa.

    Args:
        company_id: UUID da empresa.
        db: Sessão assíncrona do banco de dados.

    Returns:
        TrendsResponse com lista de pontos temporais ordenados por data_inicio.
    """
    repo = _build_dashboard_repo(db)
    trends_data = await repo.get_trends(company_id=company_id)

    tendencias = [
        TrendPoint(
            campaign_id=t["campaign_id"],
            campaign_nome=t["campaign_nome"],
            data_inicio=t["data_inicio"],
            score_geral=t["score_geral"],
            nivel_geral=t["nivel_geral"],
        )
        for t in trends_data
    ]

    return TrendsResponse(tendencias=tendencias)


# ===========================================================================
# Módulo 06 — Dashboard principal (parâmetro variável /{campaign_id})
# ===========================================================================


@router.get(
    "/{campaign_id}",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard analítico da campanha",
    description=(
        "Retorna o dashboard completo de uma campanha: resumo executivo, "
        "scores por dimensão HSE-IT e heatmap setor×dimensão paginado. "
        "Todos os dados são lidos de fact_score_dimensao — zero cálculos em runtime. "
        "O heatmap é paginado pelo parâmetro page/page_size sobre dim_estrutura. "
        "Filtros opcionais por unidade, setor e dimensão (Módulo 09)."
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
    repo = _build_dashboard_repo(db)

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
    # 3. Heatmap paginado com filtros opcionais (Módulo 09)
    # ------------------------------------------------------------------
    heatmap_data, total_estruturas = await repo.get_heatmap(
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
        unidade_id=unidade_id,
        setor_id=setor_id,
        dimensao=dimensao,
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


# ===========================================================================
# Módulo 09 — Sub-rotas de /{campaign_id} com caminho adicional
# ===========================================================================


@router.get(
    "/{campaign_id}/heatmap",
    response_model=HeatmapResponse,
    status_code=status.HTTP_200_OK,
    summary="Heatmap setor×dimensão com filtros",
    description=(
        "Retorna a matriz setor×dimensão paginada com suporte a filtros por "
        "unidade, setor e dimensão. Paginação por dim_estrutura (Regra R4). "
        "Todos os dados vêm de fact_score_dimensao (Regra R3)."
    ),
)
async def get_heatmap(
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
    unidade_id: Annotated[
        UUID | None,
        Query(description="Filtrar por unidade organizacional."),
    ] = None,
    setor_id: Annotated[
        UUID | None,
        Query(description="Filtrar por setor."),
    ] = None,
    dimensao: Annotated[
        str | None,
        Query(description="Filtrar por dimensão HSE-IT específica."),
    ] = None,
) -> HeatmapResponse:
    """Retorna o heatmap setor×dimensão paginado com filtros opcionais.

    Args:
        campaign_id: UUID da campanha.
        db: Sessão assíncrona do banco de dados.
        page: Página atual (1-indexed).
        page_size: Estruturas por página (máximo 100).
        unidade_id: Filtro opcional por unidade organizacional.
        setor_id: Filtro opcional por setor.
        dimensao: Filtro opcional por dimensão HSE-IT.

    Returns:
        HeatmapResponse com cells paginadas e metadados de paginação.
    """
    repo = _build_dashboard_repo(db)
    cells_data, total_estruturas = await repo.get_heatmap(
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
        unidade_id=unidade_id,
        setor_id=setor_id,
        dimensao=dimensao,
    )

    cells = [
        HeatmapCell(
            dim_estrutura_id=cell["dim_estrutura_id"],
            dimensao=cell["dimensao"],
            score_medio=cell["score_medio"],
            nivel_risco=cell["nivel_risco"],
            unidade_nome=cell.get("unidade_nome"),
            setor_nome=cell.get("setor_nome"),
            cargo_nome=cell.get("cargo_nome"),
        )
        for cell in cells_data
    ]

    total_pages = math.ceil(total_estruturas / page_size) if total_estruturas > 0 else 0

    pagination = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total_estruturas,
        pages=total_pages,
    )

    return HeatmapResponse(cells=cells, pagination=pagination)


@router.get(
    "/{campaign_id}/top-risks",
    response_model=TopRisksResponse,
    status_code=status.HTTP_200_OK,
    summary="Top 5 combinações setor+dimensão com maior risco",
    description=(
        "Retorna as 5 combinações de setor e dimensão HSE-IT com os menores scores "
        "(maior risco psicossocial) para a campanha. Sem paginação — sempre até 5 itens. "
        "Todos os dados vêm de fact_score_dimensao (Regra R3)."
    ),
)
async def get_top_risks(
    campaign_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TopRisksResponse:
    """Retorna as 5 combinações setor+dimensão com maior risco da campanha.

    Args:
        campaign_id: UUID da campanha.
        db: Sessão assíncrona do banco de dados.

    Returns:
        TopRisksResponse com até 5 itens ordenados por score crescente.
    """
    repo = _build_dashboard_repo(db)
    risks_data = await repo.get_top_risks(campaign_id=campaign_id)

    top_risks = [
        TopRiskItem(
            dim_estrutura_id=item["dim_estrutura_id"],
            dimensao=item["dimensao"],
            score_medio=item["score_medio"],
            nivel_risco=item["nivel_risco"],
            unidade_nome=item.get("unidade_nome"),
            setor_nome=item.get("setor_nome"),
            cargo_nome=item.get("cargo_nome"),
        )
        for item in risks_data
    ]

    return TopRisksResponse(top_risks=top_risks)
