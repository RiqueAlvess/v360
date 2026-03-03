"""Schemas Pydantic para submissão de survey responses."""
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    texto_livre: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Campo opcional: como você está se sentindo na empresa?",
    )
    consentimento_texto_livre: bool = Field(
        default=False,
        description=(
            "LGPD: consentimento explícito para análise do texto livre. "
            "Obrigatório quando texto_livre está preenchido."
        ),
    )

    @model_validator(mode="after")
    def validar_consentimento(self) -> "SurveyResponseSubmitRequest":
        """Garante que texto_livre só é aceito com consentimento explícito.

        Raises:
            ValueError: Se texto_livre for fornecido sem consentimento_texto_livre=True.
        """
        if self.texto_livre and not self.consentimento_texto_livre:
            raise ValueError(
                "consentimento_texto_livre deve ser True quando texto_livre é informado."
            )
        return self


class SurveyResponseSubmitResponse(BaseModel):
    """Resposta após submissão bem-sucedida de uma resposta de pesquisa."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(..., description="UUID da resposta criada.")
    campaign_id: str = Field(..., description="UUID da campanha.")
    mensagem: str = Field(
        ..., description="Confirmação de recebimento da resposta."
    )
