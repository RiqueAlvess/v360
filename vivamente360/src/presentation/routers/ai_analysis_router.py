"""Router do módulo de Análise por IA via OpenRouter (Módulo 06).

Regra R2: Controllers/Routers só validam entrada e delegam.
Regra R4: Todos os endpoints de listagem têm paginação (page + page_size).
Regra R1: Type hints completos em todos os parâmetros de função.

Regra inviolável: Nenhum endpoint chama o OpenRouter diretamente.
Toda análise de IA é enfileirada via task_queue → RunAiAnalysisHandler.

Endpoints implementados:
    POST   /ai-analyses/request                        — solicita análise (enfileira)
    GET    /ai-analyses/{analysis_id}                  — status/resultado (polling)
    GET    /ai-analyses?campaign_id={id}&page=1        — lista análises da campanha
    GET    /ai-analyses/{campaign_id}/summary          — resumo agregado da campanha
"""
import math
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.ai_analysis_repository import (
    SQLAiAnalysisRepository,
)
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.ai_analysis_schemas import (
    AiAnalysisCreatedResponse,
    AiAnalysisListResponse,
    AiAnalysisPaginationMeta,
    AiAnalysisRequest,
    AiAnalysisResponse,
    AiAnalysisSummaryResponse,
    PorSetorSummary,
    RecomendacaoPriorizada,
)

router: APIRouter = APIRouter(prefix="/ai-analyses", tags=["ai-analyses"])

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


# ---------------------------------------------------------------------------
# POST /ai-analyses/request
# ---------------------------------------------------------------------------


@router.post(
    "/request",
    response_model=AiAnalysisCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicita uma análise de IA para uma campanha/setor",
    description=(
        "Cria um registro de análise com status 'pending' e enfileira a tarefa "
        "'run_ai_analysis' na task_queue. O processamento ocorre de forma assíncrona "
        "— sem bloquear o request. Use o analysis_id retornado para fazer polling "
        "no endpoint GET /ai-analyses/{analysis_id} até status='completed'. "
        "Rate limit: máximo 10 análises por empresa por hora."
    ),
)
async def request_analysis(
    body: AiAnalysisRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiAnalysisCreatedResponse:
    """Enfileira uma análise de IA sem bloquear o request.

    Args:
        body: Dados da análise solicitada (campaign_id, tipo, setor_id, dimensao).
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.

    Returns:
        AiAnalysisCreatedResponse com analysis_id e status='pending'.

    Raises:
        HTTP 422: Se o tipo de análise for inválido.
    """
    repo = SQLAiAnalysisRepository(db)

    # Criar registro de análise com status 'pending'
    analysis = await repo.create(
        company_id=current_user.company_id,
        campaign_id=body.campaign_id,
        tipo=body.tipo,
        setor_id=body.setor_id,
        dimensao=body.dimensao,
    )
    await db.commit()
    await db.refresh(analysis)

    # Enfileirar a tarefa de processamento assíncrono
    task_service = TaskService(db)
    await task_service.enqueue(
        tipo=TaskQueueType.RUN_AI_ANALYSIS,
        payload={
            "analysis_id": str(analysis.id),
            "campaign_id": str(body.campaign_id),
            "company_id": str(current_user.company_id),
            "setor_id": str(body.setor_id) if body.setor_id else None,
            "dimensao": body.dimensao,
            "tipo": body.tipo,
        },
    )

    return AiAnalysisCreatedResponse(
        analysis_id=analysis.id,
        status="pending",
    )


# ---------------------------------------------------------------------------
# GET /ai-analyses/{analysis_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{analysis_id}",
    response_model=AiAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Retorna o status e resultado de uma análise de IA",
    description=(
        "Endpoint de polling — retorna o estado atual da análise. "
        "Faça requisições periódicas até status='completed' ou status='failed'. "
        "Quando status='completed', o campo 'resultado' contém o output da IA em JSONB. "
        "Quando status='failed', o campo 'erro' descreve o problema."
    ),
)
async def get_analysis(
    analysis_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiAnalysisResponse:
    """Retorna status e resultado de uma análise pelo UUID.

    Args:
        analysis_id: UUID da análise criada via POST /request.
        current_user: Usuário autenticado (RLS garante isolamento por empresa).
        db: Sessão assíncrona do banco de dados.

    Returns:
        AiAnalysisResponse com status atual e resultado (quando concluído).

    Raises:
        HTTP 404: Se a análise não existir ou não pertencer à empresa do usuário.
    """
    repo = SQLAiAnalysisRepository(db)
    analysis = await repo.get_by_id(analysis_id)

    if analysis is None or analysis.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Análise não encontrada: analysis_id={analysis_id}",
        )

    return AiAnalysisResponse.model_validate(analysis)


# ---------------------------------------------------------------------------
# GET /ai-analyses
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=AiAnalysisListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista análises de IA de uma campanha com paginação",
    description=(
        "Retorna as análises de IA da campanha informada via query param campaign_id. "
        "Suporta filtros opcionais por tipo e status. "
        "Ordenação: mais recentes primeiro. "
        "Padrão: page=1, page_size=20, máximo 100 por página."
    ),
)
async def list_analyses(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    campaign_id: Annotated[
        UUID,
        Query(description="UUID da campanha (obrigatório)."),
    ],
    tipo: Annotated[
        Optional[str],
        Query(
            description=(
                "Filtrar por tipo: 'sentimento', 'diagnostico' ou 'recomendacoes'."
            )
        ),
    ] = None,
    analysis_status: Annotated[
        Optional[str],
        Query(
            alias="status",
            description="Filtrar por status: 'pending', 'processing', 'completed', 'failed'.",
        ),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> AiAnalysisListResponse:
    """Lista análises da campanha com filtros opcionais e paginação.

    Args:
        current_user: Usuário autenticado (RLS garante isolamento por empresa).
        db: Sessão assíncrona do banco de dados.
        campaign_id: UUID da campanha a consultar (obrigatório via query param).
        tipo: Filtro opcional por tipo de análise.
        analysis_status: Filtro opcional por status.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 20).

    Returns:
        AiAnalysisListResponse com items e metadados de paginação.
    """
    repo = SQLAiAnalysisRepository(db)

    items, total = await repo.get_by_campaign(
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
        tipo=tipo,
        status=analysis_status,
    )

    pages: int = max(1, math.ceil(total / page_size)) if total > 0 else 1

    return AiAnalysisListResponse(
        items=[AiAnalysisResponse.model_validate(item) for item in items],
        pagination=AiAnalysisPaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=pages,
        ),
    )


# ---------------------------------------------------------------------------
# GET /ai-analyses/{campaign_id}/summary
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/summary",
    response_model=AiAnalysisSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Agrega e resume todas as análises concluídas de uma campanha",
    description=(
        "Retorna um sumário executivo de todas as análises de IA com status='completed' "
        "para a campanha informada. "
        "Inclui: totais, distribuição por setor, recomendações priorizadas. "
        "Apenas análises com status='completed' são incluídas no resultado. "
        "Análises pendentes ou com falha são contabilizadas nos totais mas não no conteúdo."
    ),
)
async def get_summary(
    campaign_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiAnalysisSummaryResponse:
    """Agrega análises concluídas da campanha em um resumo executivo.

    Args:
        campaign_id: UUID da campanha a resumir.
        current_user: Usuário autenticado (RLS garante isolamento por empresa).
        db: Sessão assíncrona do banco de dados.

    Returns:
        AiAnalysisSummaryResponse com totais, por_setor e recomendacoes_priorizadas.
    """
    repo = SQLAiAnalysisRepository(db)

    # Busca todas as análises da campanha (sem filtro de status) para totais
    all_items, total = await repo.get_by_campaign(
        campaign_id=campaign_id,
        page=1,
        page_size=_PAGE_SIZE_MAX,
    )

    # Busca apenas as concluídas para agregação de conteúdo
    completed = await repo.get_completed_by_campaign(campaign_id=campaign_id)

    # Contadores por status
    total_completed = sum(1 for i in all_items if i.status == "completed")
    total_pending = sum(
        1 for i in all_items if i.status in {"pending", "processing"}
    )
    total_failed = sum(1 for i in all_items if i.status == "failed")

    # Totais de tokens consumidos
    tokens_input_total = sum(
        (i.tokens_input or 0) for i in all_items if i.tokens_input
    )
    tokens_output_total = sum(
        (i.tokens_output or 0) for i in all_items if i.tokens_output
    )

    # Agrupar análises concluídas por setor
    por_setor_dict: dict[str, dict] = {}
    for analysis in completed:
        key = str(analysis.setor_id) if analysis.setor_id else "geral"
        if key not in por_setor_dict:
            por_setor_dict[key] = {
                "setor_id": analysis.setor_id,
                "total_analyses": 0,
                "tipos_concluidos": [],
                "ultimo_resultado": None,
                "ultimo_modelo": None,
                "tokens_total": 0,
            }
        entry = por_setor_dict[key]
        entry["total_analyses"] += 1
        if analysis.tipo not in entry["tipos_concluidos"]:
            entry["tipos_concluidos"].append(analysis.tipo)
        entry["ultimo_resultado"] = analysis.resultado
        entry["ultimo_modelo"] = analysis.model_usado
        entry["tokens_total"] += (analysis.tokens_input or 0) + (
            analysis.tokens_output or 0
        )

    por_setor: list[PorSetorSummary] = [
        PorSetorSummary(**v) for v in por_setor_dict.values()
    ]

    # Extrair e priorizar recomendações de todas as análises de diagnóstico
    recomendacoes_priorizadas: list[RecomendacaoPriorizada] = []
    prioridade_ordem: dict[str, int] = {"alta": 0, "media": 1, "baixa": 2}

    for analysis in completed:
        if analysis.tipo != "diagnostico" or not analysis.resultado:
            continue
        recs: list[dict] = analysis.resultado.get("recomendacoes", [])
        for rec in recs:
            if isinstance(rec, dict) and rec.get("titulo"):
                recomendacoes_priorizadas.append(
                    RecomendacaoPriorizada(
                        titulo=rec.get("titulo", ""),
                        prioridade=rec.get("prioridade", "media"),
                        prazo=rec.get("prazo", "90d"),
                        setor_id=analysis.setor_id,
                        analysis_id=analysis.id,
                    )
                )

    # Ordenar: alta > media > baixa, depois por prazo (imediato > 30d > 90d)
    prazo_ordem: dict[str, int] = {"imediato": 0, "30d": 1, "90d": 2}
    recomendacoes_priorizadas.sort(
        key=lambda r: (
            prioridade_ordem.get(r.prioridade, 99),
            prazo_ordem.get(r.prazo, 99),
        )
    )

    return AiAnalysisSummaryResponse(
        campaign_id=campaign_id,
        total_analyses=total,
        total_completed=total_completed,
        total_pending=total_pending,
        total_failed=total_failed,
        tokens_input_total=tokens_input_total,
        tokens_output_total=tokens_output_total,
        por_setor=por_setor,
        recomendacoes_priorizadas=recomendacoes_priorizadas,
    )
