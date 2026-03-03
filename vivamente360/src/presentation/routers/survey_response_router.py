"""Router para submissão de survey responses.

Após cada submissão, enfileira automaticamente a task 'compute_scores'
para que o worker reconstrói o Modelo Estrela de analytics de forma assíncrona.

Se o respondente forneceu texto_livre com consentimento, enfileira também
a task 'analyze_sentiment' para análise via LLM (OpenRouter).

Regra R3: O cálculo de scores NUNCA ocorre no request/response cycle.
As tasks são apenas enfileiradas — o worker processa de forma assíncrona.
"""
import uuid
from typing import Annotated, Optional
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
from src.shared.config import settings
from src.shared.security import encrypt_data

router: APIRouter = APIRouter(prefix="/survey-responses", tags=["survey-responses"])


@router.post(
    "/campaigns/{campaign_id}",
    response_model=SurveyResponseSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submeter resposta de pesquisa",
    description=(
        "Registra uma resposta anônima para a campanha e enfileira automaticamente "
        "a task 'compute_scores' para reconstruir o Modelo Estrela de analytics. "
        "Se texto_livre for fornecido com consentimento, enfileira também "
        "'analyze_sentiment'. O cálculo ocorre de forma assíncrona."
    ),
)
async def submit_survey_response(
    campaign_id: UUID,
    body: SurveyResponseSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SurveyResponseSubmitResponse:
    """Persiste a resposta e enfileira tasks para processamento assíncrono.

    Fluxo:
    1. Criptografar texto_livre (AES-256-GCM) se fornecido com consentimento.
    2. Criar SurveyResponse com respostas JSONB e texto criptografado.
    3. Enfileirar task 'compute_scores' com campaign_id.
    4. Se texto_livre presente, enfileirar task 'analyze_sentiment'.
    5. Commitar todas as operações atomicamente.
    6. Retornar confirmação (cálculo ocorre em background).

    Args:
        campaign_id: UUID da campanha à qual a resposta pertence.
        body: Dicionário de respostas por dimensão HSE-IT + campo livre opcional.
        db: Sessão assíncrona do banco de dados.

    Returns:
        SurveyResponseSubmitResponse com id da resposta criada.
    """
    # 1. Criptografar texto_livre se fornecido (LGPD: dado sensível em repouso)
    texto_livre_criptografado: Optional[str] = None
    if body.texto_livre and body.consentimento_texto_livre:
        texto_livre_criptografado = encrypt_data(body.texto_livre, settings.ENCRYPTION_KEY)

    # 2. Criar SurveyResponse
    response_id = uuid.uuid4()
    survey_response = SurveyResponse(
        id=response_id,
        campaign_id=campaign_id,
        respostas=body.respostas,
        anonimizado=True,
        texto_livre=texto_livre_criptografado,
    )
    db.add(survey_response)

    # 3. Enfileirar task compute_scores — processamento assíncrono (Regra R3)
    compute_task = TaskQueue(
        tipo=TaskQueueType.COMPUTE_SCORES,
        payload={"campaign_id": str(campaign_id)},
    )
    db.add(compute_task)

    # 4. Enfileirar analyze_sentiment se texto livre foi fornecido
    if texto_livre_criptografado is not None:
        sentiment_task = TaskQueue(
            tipo=TaskQueueType.ANALYZE_SENTIMENT,
            payload={
                "survey_response_id": str(response_id),
                "campaign_id": str(campaign_id),
            },
        )
        db.add(sentiment_task)

    # 5. Commit atômico: resposta + tasks na mesma transação
    await db.commit()

    return SurveyResponseSubmitResponse(
        id=str(response_id),
        campaign_id=str(campaign_id),
        mensagem="Resposta registrada. Analytics será atualizado em breve.",
    )
