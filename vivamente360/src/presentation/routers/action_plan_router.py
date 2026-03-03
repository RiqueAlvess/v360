"""Router do módulo de Plano de Ação.

Regra R2: Controllers/Routers só validam entrada e delegam ao Service.
Regra R4: Todos os endpoints de listagem têm paginação (page + page_size).
Regra R1: Type hints completos em todos os parâmetros de função.

Endpoints implementados:
    GET    /action-plans/{campaign_id}                          — lista paginada com resumo
    POST   /action-plans/{campaign_id}                          — cria plano
    GET    /action-plans/{campaign_id}/{plan_id}                — detalhe com evidências
    PATCH  /action-plans/{campaign_id}/{plan_id}                — atualização parcial
    PATCH  /action-plans/{campaign_id}/{plan_id}/status         — transição de status
    DELETE /action-plans/{campaign_id}/{plan_id}                — soft delete (cancelado)
    POST   /action-plans/{campaign_id}/{plan_id}/evidencias     — registra evidência
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.action_plan_service import ActionPlanService
from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.action_plan_repository import SQLActionPlanRepository
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.action_plan_schemas import (
    ActionPlanCreate,
    ActionPlanDetailResponse,
    ActionPlanEvidenciaCreate,
    ActionPlanEvidenciaResponse,
    ActionPlanListResponse,
    ActionPlanPaginationMeta,
    ActionPlanResponse,
    ActionPlanResumo,
    ActionPlanStatusUpdate,
    ActionPlanUpdate,
)

router: APIRouter = APIRouter(prefix="/action-plans", tags=["action-plans"])

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


def _build_service(db: AsyncSession) -> ActionPlanService:
    """Constrói o ActionPlanService com as dependências corretas para a requisição."""
    return ActionPlanService(
        action_plan_repo=SQLActionPlanRepository(db),
        db=db,
    )


# ---------------------------------------------------------------------------
# GET /action-plans/{campaign_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}",
    response_model=ActionPlanListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista planos de ação de uma campanha",
    description=(
        "Retorna os planos de ação da campanha com filtros opcionais por status, "
        "dimensão HSE-IT, unidade organizacional e nível de risco. "
        "Inclui o resumo global da campanha (total e contagem por status) "
        "e metadados de paginação. "
        "O resumo reflete TODOS os planos da campanha, independente dos filtros aplicados."
    ),
)
async def list_action_plans(
    campaign_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[
        Optional[ActionPlanStatus],
        Query(alias="status", description="Filtrar por status do plano."),
    ] = None,
    dimensao: Annotated[
        Optional[str],
        Query(description="Filtrar por dimensão HSE-IT (ex: 'demandas', 'controle')."),
    ] = None,
    unidade_id: Annotated[
        Optional[UUID],
        Query(description="Filtrar por UUID da unidade organizacional."),
    ] = None,
    nivel_risco: Annotated[
        Optional[NivelRisco],
        Query(description="Filtrar por nível de risco."),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> ActionPlanListResponse:
    """Lista planos de ação com resumo por status e paginação.

    Args:
        campaign_id: UUID da campanha a consultar.
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.
        status_filter: Filtro opcional por status.
        dimensao: Filtro opcional por dimensão HSE-IT.
        unidade_id: Filtro opcional por unidade organizacional.
        nivel_risco: Filtro opcional por nível de risco.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 20).

    Returns:
        ActionPlanListResponse com items, resumo e pagination.
    """
    service = _build_service(db)
    data = await service.list_plans(
        campaign_id=campaign_id,
        status=status_filter,
        dimensao=dimensao,
        unidade_id=unidade_id,
        nivel_risco=nivel_risco,
        page=page,
        page_size=page_size,
    )

    items_response = [ActionPlanResponse.model_validate(item) for item in data["items"]]
    resumo_data = data["resumo"]
    pagination_data = data["pagination"]

    return ActionPlanListResponse(
        items=items_response,
        resumo=ActionPlanResumo(
            total=resumo_data["total"],
            por_status=resumo_data["por_status"],
        ),
        pagination=ActionPlanPaginationMeta(
            page=pagination_data["page"],
            page_size=pagination_data["page_size"],
            total=pagination_data["total"],
            pages=pagination_data["pages"],
        ),
    )


# ---------------------------------------------------------------------------
# POST /action-plans/{campaign_id}
# ---------------------------------------------------------------------------


@router.post(
    "/{campaign_id}",
    response_model=ActionPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria um novo plano de ação para uma campanha",
    description=(
        "Cria um plano de ação vinculado à campanha e à dimensão de risco informada. "
        "Apenas usuários com role 'admin' ou 'manager' podem criar planos. "
        "O status inicial é sempre 'pendente'."
    ),
)
async def create_action_plan(
    campaign_id: UUID,
    body: ActionPlanCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionPlanResponse:
    """Cria um novo plano de ação vinculado à campanha.

    Args:
        campaign_id: UUID da campanha à qual o plano pertence.
        body: Payload com os dados do plano a criar.
        current_user: Usuário autenticado (user_id, company_id e role do JWT).
        db: Sessão assíncrona do banco de dados.

    Returns:
        ActionPlanResponse com o plano criado e id gerado.
    """
    service = _build_service(db)
    plan = await service.create_plan(
        campaign_id=campaign_id,
        company_id=current_user.company_id,
        titulo=body.titulo,
        descricao=body.descricao,
        nivel_risco=body.nivel_risco,
        prazo=body.prazo,
        created_by=current_user.user_id,
        user_role=current_user.role,
        dimensao=body.dimensao,
        unidade_id=body.unidade_id,
        setor_id=body.setor_id,
        responsavel_id=body.responsavel_id,
        responsavel_externo=body.responsavel_externo,
    )
    await db.commit()
    await db.refresh(plan)
    return ActionPlanResponse.model_validate(plan)


# ---------------------------------------------------------------------------
# GET /action-plans/{campaign_id}/{plan_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/{plan_id}",
    response_model=ActionPlanDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retorna um plano de ação com suas evidências",
    description=(
        "Retorna os dados completos do plano de ação identificado por plan_id, "
        "incluindo a lista de evidências (file_assets) vinculadas. "
        "O acesso ao arquivo físico se dá via signed URLs geradas pelo Módulo 01."
    ),
)
async def get_action_plan(
    campaign_id: UUID,
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionPlanDetailResponse:
    """Retorna plano completo com evidências.

    Args:
        campaign_id: UUID da campanha (usado para consistência de URL).
        plan_id: UUID do plano a buscar.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        ActionPlanDetailResponse com o plano e suas evidências.
    """
    service = _build_service(db)
    plan, evidencias = await service.get_plan(
        plan_id=plan_id,
        company_id=current_user.company_id,
    )

    return ActionPlanDetailResponse(
        plan=ActionPlanResponse.model_validate(plan),
        evidencias=[
            ActionPlanEvidenciaResponse(
                id=e.id,
                nome_original=e.nome_original,
                content_type=e.content_type,
                tamanho_bytes=e.tamanho_bytes,
                created_by=e.created_by,
                created_at=e.created_at,
            )
            for e in evidencias
        ],
    )


# ---------------------------------------------------------------------------
# PATCH /action-plans/{campaign_id}/{plan_id}
# ---------------------------------------------------------------------------


@router.patch(
    "/{campaign_id}/{plan_id}",
    response_model=ActionPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Atualiza campos de um plano de ação (PATCH parcial)",
    description=(
        "Atualiza apenas os campos informados no body. "
        "Campos ausentes ou null são ignorados. "
        "Não é possível editar planos com status 'concluido' ou 'cancelado'. "
        "Apenas usuários com role 'admin' ou 'manager' podem atualizar planos."
    ),
)
async def update_action_plan(
    campaign_id: UUID,
    plan_id: UUID,
    body: ActionPlanUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionPlanResponse:
    """Atualiza campos parciais de um plano de ação.

    Args:
        campaign_id: UUID da campanha (consistência de URL).
        plan_id: UUID do plano a atualizar.
        body: Campos parciais a atualizar.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        ActionPlanResponse com o plano atualizado.
    """
    service = _build_service(db)
    plan = await service.update_plan(
        plan_id=plan_id,
        company_id=current_user.company_id,
        user_role=current_user.role,
        titulo=body.titulo,
        descricao=body.descricao,
        dimensao=body.dimensao,
        unidade_id=body.unidade_id,
        setor_id=body.setor_id,
        responsavel_id=body.responsavel_id,
        responsavel_externo=body.responsavel_externo,
        nivel_risco=body.nivel_risco,
        prazo=body.prazo,
    )
    await db.commit()
    await db.refresh(plan)
    return ActionPlanResponse.model_validate(plan)


# ---------------------------------------------------------------------------
# PATCH /action-plans/{campaign_id}/{plan_id}/status
# ---------------------------------------------------------------------------


@router.patch(
    "/{campaign_id}/{plan_id}/status",
    response_model=ActionPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Altera o status de um plano de ação",
    description=(
        "Transiciona o status do plano. "
        "Ao definir status='concluido', o campo concluido_em é preenchido automaticamente. "
        "Aceita uma observação opcional registrada no payload da notificação assíncrona. "
        "Apenas usuários com role 'admin' ou 'manager' podem alterar status."
    ),
)
async def update_action_plan_status(
    campaign_id: UUID,
    plan_id: UUID,
    body: ActionPlanStatusUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionPlanResponse:
    """Transiciona o status de um plano de ação.

    Args:
        campaign_id: UUID da campanha (consistência de URL).
        plan_id: UUID do plano a atualizar.
        body: Novo status e observação opcional.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        ActionPlanResponse com status atualizado e concluido_em quando aplicável.
    """
    service = _build_service(db)
    plan = await service.update_status(
        plan_id=plan_id,
        company_id=current_user.company_id,
        user_role=current_user.role,
        new_status=body.status,
        observacao=body.observacao,
    )
    await db.commit()
    await db.refresh(plan)
    return ActionPlanResponse.model_validate(plan)


# ---------------------------------------------------------------------------
# DELETE /action-plans/{campaign_id}/{plan_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{campaign_id}/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancela um plano de ação (soft delete)",
    description=(
        "Marca o plano como 'cancelado' — sem hard delete. "
        "Planos cancelados permanecem no banco para fins de auditoria. "
        "Apenas usuários com role 'admin' ou 'manager' podem cancelar planos."
    ),
)
async def delete_action_plan(
    campaign_id: UUID,
    plan_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete de um plano de ação via status='cancelado'.

    Args:
        campaign_id: UUID da campanha (consistência de URL).
        plan_id: UUID do plano a cancelar.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.
    """
    service = _build_service(db)
    await service.cancel_plan(
        plan_id=plan_id,
        company_id=current_user.company_id,
        user_role=current_user.role,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# POST /action-plans/{campaign_id}/{plan_id}/evidencias
# ---------------------------------------------------------------------------


@router.post(
    "/{campaign_id}/{plan_id}/evidencias",
    response_model=ActionPlanEvidenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra metadados de uma evidência de conclusão do plano",
    description=(
        "Registra os metadados de um arquivo de evidência previamente enviado "
        "ao Cloudflare R2 via Módulo 01 (File Management). "
        "O campo storage_key deve conter a chave do arquivo no R2 após o upload. "
        "Delega para POST /files/upload com contexto='plano_acao'."
    ),
)
async def add_evidencia(
    campaign_id: UUID,
    plan_id: UUID,
    body: ActionPlanEvidenciaCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionPlanEvidenciaResponse:
    """Registra metadados de evidência vinculada ao plano.

    Args:
        campaign_id: UUID da campanha (consistência de URL).
        plan_id: UUID do plano ao qual a evidência pertence.
        body: Metadados do arquivo (nome, tamanho, content_type, storage_key).
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        ActionPlanEvidenciaResponse com os metadados registrados e id gerado.
    """
    service = _build_service(db)
    asset = await service.add_evidencia(
        plan_id=plan_id,
        company_id=current_user.company_id,
        nome_original=body.nome_original,
        tamanho_bytes=body.tamanho_bytes,
        content_type=body.content_type,
        storage_key=body.storage_key,
        created_by=current_user.user_id,
    )
    await db.commit()

    return ActionPlanEvidenciaResponse(
        id=asset.id,
        nome_original=asset.nome_original,
        content_type=asset.content_type,
        tamanho_bytes=asset.tamanho_bytes,
        created_by=asset.created_by,
        created_at=asset.created_at,
    )
