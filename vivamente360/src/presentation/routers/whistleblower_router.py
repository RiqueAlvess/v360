"""Router do Canal de Denúncias Anônimo — Módulo 07.

Regra R2: Controllers/Routers só validam entrada e delegam ao Service.
Regra R4: Endpoints de listagem têm paginação obrigatória (page + page_size).
Regra R1: Type hints completos em todos os parâmetros.

SEPARAÇÃO DE ROTAS:
    - Rotas públicas (/denuncia/{slug}/...): sem autenticação JWT.
      Nenhum IP, cookie ou session é registrado. Acesso universal.
    - Rotas admin (/admin/whistleblower/...): requerem JWT com role ADMIN ou MANAGER.

FLUXO DE ANONIMATO:
    Submit → report_token exibido UMA VEZ → banco armazena apenas SHA-256.
    Consulta → denunciante usa report_token para ver resposta institucional.
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.whistleblower_service import WhistleblowerService
from src.domain.enums.whistleblower_status import WhistleblowerStatus
from src.infrastructure.database.session import get_db
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.whistleblower_repository import (
    SQLWhistleblowerRepository,
)
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.whistleblower_schemas import (
    PaginationMeta,
    WhistleblowerConsultaResponse,
    WhistleblowerListResponse,
    WhistleblowerReportResponse,
    WhistleblowerResponderRequest,
    WhistleblowerSubmitRequest,
    WhistleblowerSubmitResponse,
)
from src.shared.exceptions import ForbiddenError

# ---------------------------------------------------------------------------
# Roteadores separados: público e autenticado
# ---------------------------------------------------------------------------

# Rotas públicas — sem autenticação. Sem log de IP. Sem cookie.
public_router: APIRouter = APIRouter(
    prefix="/denuncia",
    tags=["whistleblower-publico"],
)

# Rotas autenticadas — apenas admin e manager
admin_router: APIRouter = APIRouter(
    prefix="/admin/whistleblower",
    tags=["whistleblower-admin"],
)

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


def _build_service(db: AsyncSession) -> WhistleblowerService:
    """Constrói o WhistleblowerService com suas dependências por requisição."""
    return WhistleblowerService(
        repo=SQLWhistleblowerRepository(db),
        task_service=TaskService(db),
    )


async def _set_rls_context(db: AsyncSession, company_id: UUID) -> None:
    """Configura o contexto RLS para a sessão atual com o company_id resolvido.

    Equivalente ao que get_current_user faz para rotas autenticadas,
    mas para rotas públicas onde o company_id vem do slug da URL.
    """
    await db.execute(
        text("SET LOCAL app.company_id = :company_id"),
        {"company_id": str(company_id)},
    )


# ===========================================================================
# ROTAS PÚBLICAS — Sem autenticação
# ===========================================================================


@public_router.post(
    "/{company_slug}/submit",
    response_model=WhistleblowerSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submete um relato anônimo ao canal de denúncias",
    description=(
        "Rota pública — sem autenticação JWT, sem log de IP, sem cookie. "
        "Retorna o report_token UMA ÚNICA VEZ. "
        "O banco armazena apenas o SHA-256 do token. "
        "O denunciante deve guardar o token para consultar a resposta institucional."
    ),
)
async def submit_report(
    company_slug: str,
    body: WhistleblowerSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WhistleblowerSubmitResponse:
    """Recebe e persiste relato anônimo; retorna token de acompanhamento.

    Args:
        company_slug: Identificador público da empresa na URL.
        body: Categoria, descrição e nome opcional do relato.
        db: Sessão assíncrona do banco de dados.

    Returns:
        WhistleblowerSubmitResponse com report_token (exibir SOMENTE ESTA VEZ).

    Raises:
        NotFoundError (404): Se o slug não corresponder a nenhuma empresa ativa.
        ValidationError (422): Se a descrição for muito curta.
    """
    service = _build_service(db)

    # Resolve slug → company_id (sem contexto RLS ainda)
    company_id = await service.resolve_company_slug(company_slug)

    # Ativa RLS para a sessão com o company_id resolvido
    await _set_rls_context(db, company_id)

    result = await service.submit(
        company_id=company_id,
        categoria=body.categoria,
        descricao=body.descricao,
        nome_opcional=body.nome_opcional,
    )
    await db.commit()

    return WhistleblowerSubmitResponse(
        report_token=result["report_token"],
    )


@public_router.get(
    "/{company_slug}/consulta",
    response_model=WhistleblowerConsultaResponse,
    status_code=status.HTTP_200_OK,
    summary="Consulta o status e a resposta institucional via token de acompanhamento",
    description=(
        "Rota pública — sem autenticação JWT. "
        "O denunciante informa o report_token recebido ao submeter o relato. "
        "Retorna apenas o status e a resposta institucional (quando disponível)."
    ),
)
async def consulta_report(
    company_slug: str,
    token: Annotated[
        str,
        Query(
            min_length=43,
            max_length=43,
            description="Token de acompanhamento recebido ao submeter o relato.",
        ),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WhistleblowerConsultaResponse:
    """Retorna status e resposta institucional do relato via token.

    Args:
        company_slug: Identificador público da empresa na URL.
        token: Token de acompanhamento fornecido ao denunciante no submit.
        db: Sessão assíncrona do banco de dados.

    Returns:
        WhistleblowerConsultaResponse com status e resposta_institucional (se disponível).

    Raises:
        NotFoundError (404): Se o token não corresponder a nenhum relato da empresa.
    """
    service = _build_service(db)

    company_id = await service.resolve_company_slug(company_slug)
    await _set_rls_context(db, company_id)

    data = await service.consulta(
        company_id=company_id,
        report_token=token,
    )

    return WhistleblowerConsultaResponse(
        status=data["status"],
        resposta_institucional=data["resposta_institucional"],
        respondido_em=data["respondido_em"],
    )


# ===========================================================================
# ROTAS ADMIN — Requerem JWT (role ADMIN ou MANAGER)
# ===========================================================================


@admin_router.get(
    "/",
    response_model=WhistleblowerListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista relatos do canal de denúncias (admin)",
    description=(
        "Lista todos os relatos da empresa autenticada, ordenados do mais recente. "
        "Filtrável por status. Paginação obrigatória. "
        "Não expõe token_hash — relatos não permitem identificar o denunciante."
    ),
)
async def list_reports(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Relatos por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
    status_filter: Annotated[
        Optional[str],
        Query(
            alias="status",
            description="Filtrar por status: recebido, em_analise, concluido, arquivado.",
        ),
    ] = None,
) -> WhistleblowerListResponse:
    """Lista relatos da empresa com paginação e filtro opcional.

    Args:
        current_user: Usuário autenticado (company_id e role extraídos do JWT).
        db: Sessão assíncrona do banco de dados.
        page: Página da listagem.
        page_size: Itens por página.
        status_filter: Filtro opcional por status do relato.

    Returns:
        WhistleblowerListResponse com items e pagination.
    """
    service = _build_service(db)
    data = await service.list_reports(
        company_id=current_user.company_id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )

    return WhistleblowerListResponse(
        items=[
            WhistleblowerReportResponse(
                id=r.id,
                company_id=r.company_id,
                categoria=r.categoria,
                descricao=r.descricao,
                anonimo=r.anonimo,
                nome_opcional=r.nome_opcional,
                status=r.status,
                resposta_institucional=r.resposta_institucional,
                respondido_por=r.respondido_por,
                respondido_em=r.respondido_em,
                created_at=r.created_at,
            )
            for r in data["items"]
        ],
        pagination=PaginationMeta(
            page=data["pagination"]["page"],
            page_size=data["pagination"]["page_size"],
            total=data["pagination"]["total"],
            pages=data["pagination"]["pages"],
        ),
    )


@admin_router.get(
    "/{report_id}",
    response_model=WhistleblowerReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Detalhe de um relato (admin)",
    description=(
        "Retorna os dados de um relato pelo UUID. "
        "O moderador vê o relato mas NÃO tem acesso ao token_hash — "
        "não é possível identificar o denunciante."
    ),
)
async def get_report(
    report_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WhistleblowerReportResponse:
    """Retorna detalhe de um relato específico.

    Args:
        report_id: UUID do relato.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        WhistleblowerReportResponse com todos os campos do relato (sem token_hash).

    Raises:
        NotFoundError (404): Se o relato não existir ou não pertencer à empresa.
    """
    service = _build_service(db)
    report = await service.get_report(
        report_id=report_id,
        company_id=current_user.company_id,
    )

    return WhistleblowerReportResponse(
        id=report.id,
        company_id=report.company_id,
        categoria=report.categoria,
        descricao=report.descricao,
        anonimo=report.anonimo,
        nome_opcional=report.nome_opcional,
        status=report.status,
        resposta_institucional=report.resposta_institucional,
        respondido_por=report.respondido_por,
        respondido_em=report.respondido_em,
        created_at=report.created_at,
    )


@admin_router.patch(
    "/{report_id}/responder",
    response_model=WhistleblowerReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Registra resposta institucional a um relato (admin)",
    description=(
        "Permite que admins e compliance registrem a resposta oficial da empresa. "
        "O denunciante poderá consultar esta resposta via GET /denuncia/{slug}/consulta. "
        "Status válidos: em_analise, concluido, arquivado."
    ),
)
async def respond_to_report(
    report_id: UUID,
    body: WhistleblowerResponderRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WhistleblowerReportResponse:
    """Registra a resposta institucional ao relato.

    Args:
        report_id: UUID do relato a responder.
        body: Resposta institucional e novo status.
        current_user: Usuário autenticado (deve ser ADMIN ou MANAGER).
        db: Sessão assíncrona do banco de dados.

    Returns:
        WhistleblowerReportResponse atualizado com a resposta registrada.

    Raises:
        ForbiddenError (403): Se o usuário não tiver permissão de responder.
        NotFoundError (404): Se o relato não existir ou não pertencer à empresa.
        ValidationError (422): Se o status informado não for válido para resposta.
    """
    from src.domain.enums.user_role import UserRole

    if current_user.role not in {UserRole.ADMIN, UserRole.MANAGER}:
        raise ForbiddenError(
            "Apenas administradores e gestores podem registrar respostas institucionais."
        )

    service = _build_service(db)
    report = await service.respond(
        report_id=report_id,
        company_id=current_user.company_id,
        resposta_institucional=body.resposta_institucional,
        status=WhistleblowerStatus(body.status),
        respondido_por=current_user.user_id,
    )
    await db.commit()
    await db.refresh(report)

    return WhistleblowerReportResponse(
        id=report.id,
        company_id=report.company_id,
        categoria=report.categoria,
        descricao=report.descricao,
        anonimo=report.anonimo,
        nome_opcional=report.nome_opcional,
        status=report.status,
        resposta_institucional=report.resposta_institucional,
        respondido_por=report.respondido_por,
        respondido_em=report.respondido_em,
        created_at=report.created_at,
    )
