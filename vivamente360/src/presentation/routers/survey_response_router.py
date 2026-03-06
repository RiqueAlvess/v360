"""Router para submissão e listagem de survey responses.

Após cada submissão, enfileira automaticamente a task 'compute_scores'
para que o worker reconstrói o Modelo Estrela de analytics de forma assíncrona.

Se o respondente forneceu texto_livre com consentimento, enfileira também
a task 'analyze_sentiment' para análise via LLM (OpenRouter).

Regra R3: O cálculo de scores NUNCA ocorre no request/response cycle.
As tasks são apenas enfileiradas — o worker processa de forma assíncrona.

Regra R4: O endpoint de listagem (GET) tem paginação obrigatória.
"""
import hashlib
import math
import uuid
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.models.invitation import Invitation
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.database.models.task_queue import TaskQueue
from src.infrastructure.database.session import get_db
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.survey_response_schemas import (
    SurveyResponseListItem,
    SurveyResponseListResponse,
    SurveyResponsePaginationMeta,
    SurveyResponseSubmitRequest,
    SurveyResponseSubmitResponse,
)
from src.shared.config import settings
from src.shared.exceptions import ConflictError
from src.shared.security import encrypt_data

router: APIRouter = APIRouter(prefix="/survey-responses", tags=["survey-responses"])

_limiter: Limiter = Limiter(key_func=get_remote_address)

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


# ---------------------------------------------------------------------------
# POST /survey-responses/campaigns/{campaign_id}
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}",
    response_model=SurveyResponseSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submeter resposta de pesquisa",
    description=(
        "Registra uma resposta anônima para a campanha e enfileira automaticamente "
        "a task 'compute_scores' para reconstruir o Modelo Estrela de analytics. "
        "Se texto_livre for fornecido com consentimento, enfileira também "
        "'analyze_sentiment'. O cálculo ocorre de forma assíncrona. "
        "Se invite_token for fornecido, valida o convite e marca como respondido — "
        "retorna 409 se o convite já foi utilizado."
    ),
)
@_limiter.limit("5/minute")
async def submit_survey_response(
    request: Request,
    campaign_id: UUID,
    body: SurveyResponseSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SurveyResponseSubmitResponse:
    """Persiste a resposta e enfileira tasks para processamento assíncrono.

    Fluxo:
    1. Validar invite_token (se fornecido) — 409 se já utilizado.
    2. Criptografar texto_livre (AES-256-GCM) se fornecido com consentimento.
    3. Criar SurveyResponse com respostas JSONB e texto criptografado.
    4. Marcar invitation.respondido=True (Blind Drop: sem FK na resposta).
    5. Enfileirar task 'compute_scores' com campaign_id.
    6. Se texto_livre presente, enfileirar task 'analyze_sentiment'.
    7. Commitar todas as operações atomicamente.
    8. Retornar confirmação (cálculo ocorre em background).

    Args:
        campaign_id: UUID da campanha à qual a resposta pertence.
        body: Dicionário de respostas por dimensão HSE-IT + campos opcionais.
        db: Sessão assíncrona do banco de dados.

    Returns:
        SurveyResponseSubmitResponse com id da resposta criada.

    Raises:
        ConflictError: Se o invite_token informado já foi utilizado (409).
    """
    # 1. Validar invite_token se fornecido (Blind Drop — sem FK para a resposta)
    invitation: Optional[Invitation] = None
    if body.invite_token:
        token_hash = hashlib.sha256(body.invite_token.encode()).hexdigest()
        result = await db.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )
        invitation = result.scalar_one_or_none()

        if invitation is not None and invitation.respondido:
            raise ConflictError(
                detail="Este convite já foi utilizado. Cada participante pode responder apenas uma vez."
            )

    # 2. Criptografar texto_livre se fornecido (LGPD: dado sensível em repouso)
    texto_livre_criptografado: Optional[str] = None
    if body.texto_livre and body.consentimento_texto_livre:
        texto_livre_criptografado = encrypt_data(body.texto_livre, settings.ENCRYPTION_KEY)

    # 3. Criar SurveyResponse
    response_id = uuid.uuid4()
    survey_response = SurveyResponse(
        id=response_id,
        campaign_id=campaign_id,
        respostas=body.respostas,
        anonimizado=True,
        texto_livre=texto_livre_criptografado,
    )
    db.add(survey_response)

    # 4. Marcar invitation como respondida (Blind Drop: sem FK na survey_response)
    if invitation is not None:
        invitation.respondido = True

    # 5. Enfileirar task compute_scores — processamento assíncrono (Regra R3)
    compute_task = TaskQueue(
        tipo=TaskQueueType.COMPUTE_SCORES,
        payload={"campaign_id": str(campaign_id)},
    )
    db.add(compute_task)

    # 6. Enfileirar analyze_sentiment se texto livre foi fornecido
    if texto_livre_criptografado is not None:
        sentiment_task = TaskQueue(
            tipo=TaskQueueType.ANALYZE_SENTIMENT,
            payload={
                "survey_response_id": str(response_id),
                "campaign_id": str(campaign_id),
            },
        )
        db.add(sentiment_task)

    # 7. Commit atômico: resposta + invitation update + tasks na mesma transação
    await db.commit()

    return SurveyResponseSubmitResponse(
        id=str(response_id),
        campaign_id=str(campaign_id),
        mensagem="Resposta registrada. Analytics será atualizado em breve.",
    )


# ---------------------------------------------------------------------------
# GET /survey-responses/
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=SurveyResponseListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista respostas de uma campanha (dados anonimizados)",
    description=(
        "Retorna respostas anonimizadas de uma campanha. Requer autenticação. "
        "Nenhum dado identificável (texto_livre, email) é exposto — apenas "
        "metadados da resposta (id, created_at, sentimento). "
        "Regra R4: paginação obrigatória via page e page_size."
    ),
)
async def list_survey_responses(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    campaign_id: Annotated[
        UUID,
        Query(description="UUID da campanha cujas respostas serão listadas."),
    ],
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Respostas por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> SurveyResponseListResponse:
    """Lista respostas anonimizadas de uma campanha com paginação.

    Apenas campos não-identificáveis são expostos: id, campaign_id,
    anonimizado, sentimento (classificação qualitativa) e created_at.
    O texto_livre e demais dados sensíveis nunca são retornados.

    Args:
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.
        campaign_id: UUID da campanha.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 20).

    Returns:
        SurveyResponseListResponse com items anonimizados e pagination.
    """
    from sqlalchemy import func

    # Contar total de respostas para a campanha
    count_stmt = (
        select(func.count(SurveyResponse.id))
        .where(SurveyResponse.campaign_id == campaign_id)
    )
    count_result = await db.execute(count_stmt)
    total: int = count_result.scalar_one() or 0

    # Buscar respostas paginadas — apenas campos anonimizados
    offset = (page - 1) * page_size
    items_stmt = (
        select(
            SurveyResponse.id,
            SurveyResponse.campaign_id,
            SurveyResponse.anonimizado,
            SurveyResponse.sentimento,
            SurveyResponse.created_at,
        )
        .where(SurveyResponse.campaign_id == campaign_id)
        .order_by(SurveyResponse.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_stmt)
    rows = items_result.all()

    pages = math.ceil(total / page_size) if total > 0 else 0

    items: list[SurveyResponseListItem] = [
        SurveyResponseListItem(
            id=row.id,
            campaign_id=row.campaign_id,
            anonimizado=row.anonimizado,
            sentimento=row.sentimento.value if row.sentimento else None,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return SurveyResponseListResponse(
        items=items,
        pagination=SurveyResponsePaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=pages,
        ),
    )
