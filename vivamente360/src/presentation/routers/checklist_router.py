"""Router do módulo de Checklist NR-1.

Regra R2: Controllers/Routers só validam entrada e delegam ao Service.
Regra R4: Todos os endpoints de listagem têm paginação (page + page_size).
Regra R1: Type hints completos em todos os parâmetros de função.

Endpoints implementados:
    GET    /checklists/{campaign_id}                         — lista com progresso
    PATCH  /checklists/items/{item_id}/toggle                — toggle de conclusão
    GET    /checklists/items/{item_id}/evidencias            — lista evidências
    POST   /checklists/items/{item_id}/evidencias            — adiciona evidência
    DELETE /checklists/items/{item_id}/evidencias/{file_id}  — soft delete evidência
    GET    /checklists/{campaign_id}/export                  — exportação (stub Módulo 05)
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.checklist_service import ChecklistService
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.checklist_repository import SQLChecklistRepository
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.checklist_schemas import (
    ChecklistItemResponse,
    ChecklistListResponse,
    ChecklistPaginationMeta,
    ChecklistProgresso,
    CreateEvidenciaRequest,
    EvidenciaResponse,
    ToggleItemRequest,
)

router: APIRouter = APIRouter(prefix="/checklists", tags=["checklists"])

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 50


def _build_service(db: AsyncSession) -> ChecklistService:
    """Constrói o ChecklistService com as dependências corretas para a requisição."""
    return ChecklistService(SQLChecklistRepository(db))


def _to_item_response(item: object) -> ChecklistItemResponse:
    """Converte ChecklistItem ORM (com template carregado) para schema de resposta.

    O template é acessado via lazy="joined" definido no modelo ChecklistItem,
    portanto já está disponível sem consulta adicional ao banco.
    """
    from src.infrastructure.database.models.checklist_item import ChecklistItem as ItemModel

    m: ItemModel = item  # type: ignore[assignment]
    return ChecklistItemResponse(
        id=m.id,
        campaign_id=m.campaign_id,
        template_id=m.template_id,
        company_id=m.company_id,
        # Campos desnormalizados do template
        codigo=m.template.codigo,
        descricao=m.template.descricao,
        categoria=m.template.categoria,
        obrigatorio=m.template.obrigatorio,
        prazo_dias=m.template.prazo_dias,
        ordem=m.template.ordem,
        # Estado do item
        concluido=m.concluido,
        concluido_em=m.concluido_em,
        concluido_por=m.concluido_por,
        observacao=m.observacao,
        prazo=m.prazo,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# GET /checklists/{campaign_id}/export
# Deve ser declarado ANTES de GET /{campaign_id} para evitar conflito de rota.
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}/export",
    status_code=status.HTTP_200_OK,
    summary="Exportação do checklist NR-1 (stub — Módulo 05)",
    description=(
        "Endpoint reservado para integração com o Módulo 05 (Relatórios). "
        "Retorna informação indicando que a geração de PDF é assíncrona."
    ),
    tags=["checklists", "export"],
)
async def export_checklist(
    campaign_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    """Stub de exportação — delegará para o Módulo 05 quando implementado.

    Args:
        campaign_id: UUID da campanha a exportar.
        current_user: Usuário autenticado via JWT.
        db: Sessão assíncrona do banco de dados.

    Returns:
        Mensagem indicando que a geração foi enfileirada.
    """
    # TODO (Módulo 05): enfileirar task GENERATE_REPORT e retornar task_id
    return {
        "mensagem": (
            f"A geração do relatório PDF para a campanha {campaign_id} "
            "será implementada pelo Módulo 05 (Relatórios). "
            "O endpoint estará disponível em breve."
        ),
        "campaign_id": str(campaign_id),
        "status": "not_implemented",
    }


# ---------------------------------------------------------------------------
# GET /checklists/{campaign_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{campaign_id}",
    response_model=ChecklistListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista itens do checklist NR-1 de uma campanha",
    description=(
        "Retorna os itens do checklist da campanha com filtros opcionais por categoria "
        "e status de conclusão. Inclui o indicador de progresso global da campanha "
        "(total, concluídos, percentual) e metadados de paginação. "
        "O progresso reflete TODOS os itens da campanha, independente dos filtros aplicados."
    ),
)
async def get_checklist(
    campaign_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    categoria: Annotated[
        Optional[str],
        Query(description="Filtrar por categoria NR-1 (ex: 'Identificação', 'GRO')."),
    ] = None,
    concluido: Annotated[
        Optional[bool],
        Query(description="Filtrar por status: true=concluídos, false=pendentes."),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> ChecklistListResponse:
    """Lista itens do checklist com progresso e paginação.

    Args:
        campaign_id: UUID da campanha a consultar.
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.
        categoria: Filtro opcional por categoria NR-1.
        concluido: Filtro opcional por status de conclusão.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 50).

    Returns:
        ChecklistListResponse com items, progresso e pagination.
    """
    service = _build_service(db)
    data = await service.get_checklist(
        campaign_id=campaign_id,
        categoria=categoria,
        concluido=concluido,
        page=page,
        page_size=page_size,
    )

    items_response = [_to_item_response(item) for item in data["items"]]
    progresso_data = data["progresso"]
    pagination_data = data["pagination"]

    return ChecklistListResponse(
        items=items_response,
        progresso=ChecklistProgresso(
            total=progresso_data["total"],
            concluidos=progresso_data["concluidos"],
            percentual=progresso_data["percentual"],
        ),
        pagination=ChecklistPaginationMeta(
            page=pagination_data["page"],
            page_size=pagination_data["page_size"],
            total=pagination_data["total"],
            pages=pagination_data["pages"],
        ),
    )


# ---------------------------------------------------------------------------
# PATCH /checklists/items/{item_id}/toggle
# ---------------------------------------------------------------------------


@router.patch(
    "/items/{item_id}/toggle",
    response_model=ChecklistItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Alterna o status de conclusão de um item do checklist",
    description=(
        "Marca ou desmarca um item como concluído. "
        "Ao concluir (concluido=true), registra concluido_em e concluido_por automaticamente. "
        "Ao reabrir (concluido=false), limpa esses campos. "
        "Aceita uma observação opcional registrada junto à alteração."
    ),
)
async def toggle_checklist_item(
    item_id: UUID,
    body: ToggleItemRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChecklistItemResponse:
    """Alterna o estado de conclusão de um item do checklist.

    Args:
        item_id: UUID do item a ser alterado.
        body: Payload com o novo estado e observação opcional.
        current_user: Usuário autenticado (user_id e company_id extraídos do JWT).
        db: Sessão assíncrona do banco de dados.

    Returns:
        O ChecklistItemResponse atualizado com concluido_em e concluido_por.
    """
    service = _build_service(db)
    item = await service.toggle_item(
        item_id=item_id,
        concluido=body.concluido,
        user_id=current_user.user_id,
        company_id=current_user.company_id,
        observacao=body.observacao,
    )
    await db.commit()
    # Recarregar o item com template após commit
    await db.refresh(item, ["template"])
    return _to_item_response(item)


# ---------------------------------------------------------------------------
# GET /checklists/items/{item_id}/evidencias
# ---------------------------------------------------------------------------


@router.get(
    "/items/{item_id}/evidencias",
    response_model=list[EvidenciaResponse],
    status_code=status.HTTP_200_OK,
    summary="Lista evidências vinculadas a um item do checklist",
    description=(
        "Retorna os metadados dos arquivos de evidência (file_assets) vinculados "
        "ao item. O arquivo físico reside no Cloudflare R2 e é acessado via "
        "signed URLs geradas sob demanda (Módulo 01 — File Management)."
    ),
)
async def get_evidencias(
    item_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[EvidenciaResponse]:
    """Lista evidências ativas vinculadas ao item.

    Args:
        item_id: UUID do item do checklist.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        Lista de EvidenciaResponse (excluindo arquivos com soft delete).
    """
    service = _build_service(db)
    assets = await service.get_evidencias(
        item_id=item_id,
        company_id=current_user.company_id,
    )

    return [
        EvidenciaResponse(
            id=a.id,
            nome_original=a.nome_original,
            content_type=a.content_type,
            tamanho_bytes=a.tamanho_bytes,
            created_by=a.created_by,
            created_at=a.created_at,
        )
        for a in assets
    ]


# ---------------------------------------------------------------------------
# POST /checklists/items/{item_id}/evidencias
# ---------------------------------------------------------------------------


@router.post(
    "/items/{item_id}/evidencias",
    response_model=EvidenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registra metadados de uma evidência para um item do checklist",
    description=(
        "Registra os metadados de um arquivo de evidência previamente enviado "
        "ao Cloudflare R2 via Módulo 01 (File Management). "
        "O campo storage_key deve conter a chave do arquivo no R2 após o upload. "
        "Delega para POST /files/upload com contexto='checklist_evidencia'."
    ),
)
async def add_evidencia(
    item_id: UUID,
    body: CreateEvidenciaRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EvidenciaResponse:
    """Registra metadados de evidência vinculada ao item.

    Args:
        item_id: UUID do item do checklist ao qual a evidência pertence.
        body: Metadados do arquivo (nome, tamanho, content_type, storage_key).
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        EvidenciaResponse com os metadados registrados e id gerado.
    """
    service = _build_service(db)
    asset = await service.add_evidencia(
        item_id=item_id,
        company_id=current_user.company_id,
        nome_original=body.nome_original,
        tamanho_bytes=body.tamanho_bytes,
        content_type=body.content_type,
        storage_key=body.storage_key,
        created_by=current_user.user_id,
    )
    await db.commit()

    return EvidenciaResponse(
        id=asset.id,
        nome_original=asset.nome_original,
        content_type=asset.content_type,
        tamanho_bytes=asset.tamanho_bytes,
        created_by=asset.created_by,
        created_at=asset.created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /checklists/items/{item_id}/evidencias/{file_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/items/{item_id}/evidencias/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove uma evidência do item do checklist (soft delete)",
    description=(
        "Marca o file_asset como deletado (soft delete). "
        "O arquivo físico no Cloudflare R2 é removido de forma assíncrona "
        "por um worker de limpeza. Nunca realiza hard delete."
    ),
)
async def delete_evidencia(
    item_id: UUID,
    file_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete de uma evidência vinculada ao item.

    Args:
        item_id: UUID do item do checklist.
        file_id: UUID do file_asset a ser removido.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.
    """
    service = _build_service(db)
    await service.delete_evidencia(
        item_id=item_id,
        file_id=file_id,
        company_id=current_user.company_id,
    )
    await db.commit()
