"""Schemas Pydantic para submissão e listagem de survey responses."""
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Constantes de validação Likert (escala 1–5, conforme HSE-IT)
# ---------------------------------------------------------------------------

LIKERT_MIN: int = 1
LIKERT_MAX: int = 5


def _validar_score_likert(valor: Any) -> None:
    """Verifica que um valor (numérico ou lista) está na escala Likert 1–5.

    Args:
        valor: Valor a validar — int/float ou lista de int/float.

    Raises:
        ValueError: Se o valor estiver fora do intervalo [1, 5].
    """
    if isinstance(valor, (int, float)):
        if not (LIKERT_MIN <= valor <= LIKERT_MAX):
            raise ValueError(
                f"Score Likert fora do intervalo válido [{LIKERT_MIN}, {LIKERT_MAX}]: {valor}"
            )
    elif isinstance(valor, list):
        for item in valor:
            if isinstance(item, (int, float)) and not (LIKERT_MIN <= item <= LIKERT_MAX):
                raise ValueError(
                    f"Score Likert fora do intervalo válido [{LIKERT_MIN}, {LIKERT_MAX}]: {item}"
                )


# ---------------------------------------------------------------------------
# Schemas de Submissão
# ---------------------------------------------------------------------------


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
    invite_token: Optional[str] = Field(
        default=None,
        description=(
            "Token de convite recebido por e-mail. Obrigatório para campanhas "
            "com lista de convidados. Validado via SHA-256 no banco de dados."
        ),
    )

    @field_validator("respostas")
    @classmethod
    def validar_scores_likert(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Verifica que todos os scores estão na escala Likert [1, 5].

        Args:
            v: Dicionário de respostas por dimensão.

        Returns:
            Dicionário validado sem alteração.

        Raises:
            ValueError: Se qualquer score estiver fora do intervalo [1, 5].
        """
        for chave, valor in v.items():
            try:
                _validar_score_likert(valor)
            except ValueError as exc:
                raise ValueError(f"Dimensão '{chave}': {exc}") from exc
        return v

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


# ---------------------------------------------------------------------------
# Schemas de Listagem (autenticados — admins/managers)
# ---------------------------------------------------------------------------


class SurveyResponseListItem(BaseModel):
    """Item de listagem de resposta de pesquisa (dados anonimizados).

    Não expõe texto_livre nem qualquer campo identificável.
    Exibe apenas metadados para uso no painel administrativo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="UUID da resposta.")
    campaign_id: uuid.UUID = Field(..., description="UUID da campanha.")
    anonimizado: bool = Field(..., description="Indica que a resposta foi anonimizada.")
    sentimento: Optional[str] = Field(
        default=None,
        description="Classificação de sentimento (populada pelo worker).",
    )
    created_at: datetime = Field(..., description="Data/hora de submissão.")


class SurveyResponsePaginationMeta(BaseModel):
    """Metadados de paginação para listagem de respostas."""

    page: int = Field(..., ge=1, description="Página atual.")
    page_size: int = Field(..., ge=1, le=100, description="Itens por página.")
    total: int = Field(..., ge=0, description="Total de respostas na campanha.")
    pages: int = Field(..., ge=0, description="Total de páginas.")


class SurveyResponseListResponse(BaseModel):
    """Resposta paginada de listagem de survey responses."""

    items: list[SurveyResponseListItem] = Field(
        ..., description="Respostas da página atual (dados anonimizados)."
    )
    pagination: SurveyResponsePaginationMeta = Field(
        ..., description="Metadados de paginação."
    )
