"""Router para submissão de survey responses.

Após cada submissão, enfileira automaticamente a task 'compute_scores'
para que o worker reconstrói o Modelo Estrela de analytics de forma assíncrona.

Regra R3: O cálculo de scores NUNCA ocorre no request/response cycle.
A task é apenas enfileirada — o worker processa de forma assíncrona.
"""
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.database.models.task_queue import TaskQueue
from src.infrastructure.database.session import get_db
from src.presentation.schemas.survey_response_schemas import (
    SurveyResponseSubmitRequest,
    SurveyResponseSubmitResponse,
)

router: APIRouter = APIRouter(prefix="/survey-responses", tags=["survey-responses"])


@router.post(
    "/campaigns/{campaign_id}",
    response_model=SurveyResponseSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submeter resposta de pesquisa",
    description=(
        "Registra uma resposta anônima para a campanha e enfileira automaticamente "
        "a task 'compute_scores' para reconstruir o Modelo Estrela de analytics. "
        "O cálculo de scores ocorre de forma assíncrona — não bloqueia a resposta."
    ),
)
async def submit_survey_response(
    campaign_id: UUID,
    body: SurveyResponseSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SurveyResponseSubmitResponse:
    """Persiste a resposta e enfileira rebuild_analytics para processamento assíncrono.

    Fluxo:
    1. Criar SurveyResponse com as respostas JSONB.
    2. Enfileirar task 'compute_scores' com campaign_id.
    3. Commitar ambas as operações atomicamente.
    4. Retornar confirmação (o cálculo ocorre em background).

    Args:
        campaign_id: UUID da campanha à qual a resposta pertence.
        body: Dicionário de respostas por dimensão HSE-IT.
        db: Sessão assíncrona do banco de dados.

    Returns:
        SurveyResponseSubmitResponse com id da resposta criada.
    """
    # 1. Criar SurveyResponse
    survey_response = SurveyResponse(
        id=uuid.uuid4(),
        campaign_id=campaign_id,
        respostas=body.respostas,
        anonimizado=True,
    )
    db.add(survey_response)

    # 2. Enfileirar task compute_scores — processamento assíncrono (Regra R3)
    #    O worker reconstrói o Modelo Estrela para toda a campanha
    compute_task = TaskQueue(
        tipo=TaskQueueType.COMPUTE_SCORES,
        payload={"campaign_id": str(campaign_id)},
    )
    db.add(compute_task)

    # 3. Commit atômico: resposta + task na mesma transação
    await db.commit()

    return SurveyResponseSubmitResponse(
        id=str(survey_response.id),
        campaign_id=str(campaign_id),
        mensagem="Resposta registrada. Analytics será atualizado em breve.",
    )
