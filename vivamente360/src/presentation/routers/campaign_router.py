"""Router de campanhas de avaliação psicossocial.

Regra R2: Controllers/Routers só validam entrada e delegam ao Service.
Regra R4: Todos os endpoints de listagem têm paginação (page + page_size).
Regra R1: Type hints completos em todos os parâmetros de função.

Hook automático: POST /campaigns dispara a criação do checklist NR-1
completo para a campanha via CampaignService (Módulo 02).
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.campaign_service import CampaignService
from src.application.services.checklist_service import ChecklistService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.campaign_repository import SQLCampaignRepository
from src.infrastructure.repositories.checklist_repository import SQLChecklistRepository
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.checklist_schemas import (
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignResponse,
    ChecklistPaginationMeta,
)

router: APIRouter = APIRouter(prefix="/campaigns", tags=["campaigns"])

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


def _build_service(db: AsyncSession) -> CampaignService:
    """Constrói o CampaignService com todas as dependências da requisição."""
    checklist_service = ChecklistService(SQLChecklistRepository(db))
    return CampaignService(
        campaign_repo=SQLCampaignRepository(db),
        checklist_service=checklist_service,
    )


# ---------------------------------------------------------------------------
# POST /campaigns
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma nova campanha de avaliação psicossocial",
    description=(
        "Cria uma campanha com status DRAFT e, automaticamente, inicializa o checklist NR-1 "
        "completo (15+ itens canônicos) a partir dos templates cadastrados. "
        "A campanha pode ser ativada posteriormente via endpoint de atualização de status."
    ),
)
async def create_campaign(
    body: CampaignCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    """Cria campanha e inicializa o checklist NR-1 automaticamente.

    Args:
        body: Dados da campanha (nome, data_inicio, data_fim).
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.

    Returns:
        CampaignResponse com os dados da campanha criada (status=DRAFT).
    """
    service = _build_service(db)
    campaign = await service.create_campaign(
        company_id=current_user.company_id,
        nome=body.nome,
        data_inicio=body.data_inicio,
        data_fim=body.data_fim,
    )
    await db.commit()
    await db.refresh(campaign)

    return CampaignResponse(
        id=campaign.id,
        company_id=campaign.company_id,
        nome=campaign.nome,
        status=campaign.status.value,
        data_inicio=campaign.data_inicio,
        data_fim=campaign.data_fim,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /campaigns
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=CampaignListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista campanhas da empresa autenticada",
    description=(
        "Retorna as campanhas da empresa autenticada, ordenadas por data de criação "
        "descendente (mais recente primeiro), com paginação obrigatória."
    ),
)
async def list_campaigns(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Campanhas por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> CampaignListResponse:
    """Lista campanhas da empresa com paginação.

    Args:
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 20).

    Returns:
        CampaignListResponse com items e pagination.
    """
    service = _build_service(db)
    data = await service.list_campaigns(
        company_id=current_user.company_id,
        page=page,
        page_size=page_size,
    )

    return CampaignListResponse(
        items=[
            CampaignResponse(
                id=c.id,
                company_id=c.company_id,
                nome=c.nome,
                status=c.status.value,
                data_inicio=c.data_inicio,
                data_fim=c.data_fim,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in data["items"]
        ],
        pagination=ChecklistPaginationMeta(
            page=data["pagination"]["page"],
            page_size=data["pagination"]["page_size"],
            total=data["pagination"]["total"],
            pages=data["pagination"]["pages"],
        ),
    )


# ---------------------------------------------------------------------------
# GET /campaigns/{campaign_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    status_code=status.HTTP_200_OK,
    summary="Retorna detalhes de uma campanha",
    description="Retorna os dados de uma campanha pelo seu UUID. Valida que pertence à empresa autenticada.",
)
async def get_campaign(
    campaign_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignResponse:
    """Retorna uma campanha pelo UUID.

    Args:
        campaign_id: UUID da campanha a consultar.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        CampaignResponse com os dados da campanha.

    Raises:
        NotFoundError (404): Se a campanha não existir ou não pertencer à empresa.
    """
    service = _build_service(db)
    campaign = await service.get_campaign(
        campaign_id=campaign_id,
        company_id=current_user.company_id,
    )

    return CampaignResponse(
        id=campaign.id,
        company_id=campaign.company_id,
        nome=campaign.nome,
        status=campaign.status.value,
        data_inicio=campaign.data_inicio,
        data_fim=campaign.data_fim,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )
