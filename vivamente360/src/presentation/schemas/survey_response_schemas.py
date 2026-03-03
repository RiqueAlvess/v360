"""Schemas Pydantic para submissão de survey responses."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SurveyResponseSubmitRequest(BaseModel):
    """Payload para submissão de uma resposta de pesquisa."""

    model_config = ConfigDict(str_strip_whitespace=True)

    respostas: dict[str, Any] = Field(
        ...,
        description=(
            "Respostas estruturadas por dimensão HSE-IT. "
            "Cada chave é o nome de uma dimensão (ex: 'demandas', 'controle') "
            "e o valor é o score numérico (1-5) ou lista de scores."
        ),
    )


class SurveyResponseSubmitResponse(BaseModel):
    """Resposta após submissão bem-sucedida de uma resposta de pesquisa."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="UUID da resposta criada.")
    campaign_id: str = Field(..., description="UUID da campanha.")
    mensagem: str = Field(
        ..., description="Confirmação de recebimento da resposta."
    )
