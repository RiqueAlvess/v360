"""Testes unitários para survey_response_schemas.

Cobre as correções obrigatórias do Blueprint 03:
    - SurveyResponseSubmitRequest com todos os campos válidos.
    - Validação de respostas fora do range Likert (nota > 5 ou < 1).
    - Schema de anonimização: dados identificáveis não devem vazar.
    - Consentimento obrigatório para texto_livre.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.presentation.schemas.survey_response_schemas import (
    SurveyResponseListItem,
    SurveyResponseListResponse,
    SurveyResponsePaginationMeta,
    SurveyResponseSubmitRequest,
    SurveyResponseSubmitResponse,
)

# Respostas Likert válidas (valores entre 1 e 5)
VALID_RESPOSTAS: dict = {
    "demandas": 4,
    "controle": 3,
    "suporte_gestao": 4,
    "relacionamentos": 5,
    "papel_funcao": 3,
    "mudancas": 2,
    "suporte_colegas": 4,
}


# ---------------------------------------------------------------------------
# SurveyResponseSubmitRequest
# ---------------------------------------------------------------------------


class TestSurveyResponseSubmitRequest:
    def test_valid_request_minimal(self):
        """Payload mínimo (apenas respostas) é válido."""
        req = SurveyResponseSubmitRequest(respostas=VALID_RESPOSTAS)
        assert req.respostas == VALID_RESPOSTAS
        assert req.texto_livre is None
        assert req.consentimento_texto_livre is False
        assert req.invite_token is None

    def test_valid_request_all_fields(self):
        """Payload com todos os campos opcionais preenchidos é válido."""
        req = SurveyResponseSubmitRequest(
            respostas=VALID_RESPOSTAS,
            texto_livre="Ambiente de trabalho excelente.",
            consentimento_texto_livre=True,
            invite_token="abc123token",
        )
        assert req.texto_livre == "Ambiente de trabalho excelente."
        assert req.consentimento_texto_livre is True
        assert req.invite_token == "abc123token"

    def test_valid_request_likert_boundary_values(self):
        """Scores nos limites da escala Likert (1 e 5) são aceitos."""
        req = SurveyResponseSubmitRequest(
            respostas={"demandas": 1, "controle": 5}
        )
        assert req.respostas["demandas"] == 1
        assert req.respostas["controle"] == 5

    def test_valid_request_likert_list_of_scores(self):
        """Valor como lista de scores Likert válidos é aceito."""
        req = SurveyResponseSubmitRequest(
            respostas={"demandas": [1, 2, 3, 4, 5]}
        )
        assert req.respostas["demandas"] == [1, 2, 3, 4, 5]

    # --- Validação Likert ---

    def test_score_above_max_raises_422(self):
        """Score acima de 5 (máximo Likert) levanta ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SurveyResponseSubmitRequest(respostas={"demandas": 6})
        errors = exc_info.value.errors()
        assert any("respostas" in str(e["loc"]) for e in errors)

    def test_score_below_min_raises_422(self):
        """Score abaixo de 1 (mínimo Likert) levanta ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SurveyResponseSubmitRequest(respostas={"controle": 0})
        errors = exc_info.value.errors()
        assert any("respostas" in str(e["loc"]) for e in errors)

    def test_score_float_out_of_range_raises_422(self):
        """Score float fora do intervalo levanta ValidationError."""
        with pytest.raises(ValidationError):
            SurveyResponseSubmitRequest(respostas={"demandas": 5.5})

    def test_score_negative_raises_422(self):
        """Score negativo levanta ValidationError."""
        with pytest.raises(ValidationError):
            SurveyResponseSubmitRequest(respostas={"demandas": -1})

    def test_score_list_with_out_of_range_item_raises_422(self):
        """Lista com um score fora do range levanta ValidationError."""
        with pytest.raises(ValidationError):
            SurveyResponseSubmitRequest(respostas={"demandas": [1, 2, 6]})

    def test_score_float_valid_within_range(self):
        """Score float dentro do intervalo [1, 5] é aceito."""
        req = SurveyResponseSubmitRequest(respostas={"demandas": 3.5})
        assert req.respostas["demandas"] == 3.5

    # --- Validação de consentimento ---

    def test_texto_livre_without_consent_raises_422(self):
        """texto_livre sem consentimento_texto_livre=True levanta ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SurveyResponseSubmitRequest(
                respostas=VALID_RESPOSTAS,
                texto_livre="Feedback qualitativo.",
                consentimento_texto_livre=False,
            )
        errors = exc_info.value.errors()
        assert any("consentimento_texto_livre" in str(e["msg"]).lower()
                   or "consentimento" in str(e["msg"]).lower()
                   for e in errors)

    def test_texto_livre_with_consent_is_valid(self):
        """texto_livre com consentimento_texto_livre=True é válido."""
        req = SurveyResponseSubmitRequest(
            respostas=VALID_RESPOSTAS,
            texto_livre="Feedback qualitativo.",
            consentimento_texto_livre=True,
        )
        assert req.texto_livre == "Feedback qualitativo."

    def test_empty_texto_livre_without_consent_is_valid(self):
        """texto_livre None sem consentimento é válido (campo opcional)."""
        req = SurveyResponseSubmitRequest(
            respostas=VALID_RESPOSTAS,
            texto_livre=None,
            consentimento_texto_livre=False,
        )
        assert req.texto_livre is None

    def test_texto_livre_max_length_exceeded_raises_422(self):
        """texto_livre acima de 2000 caracteres levanta ValidationError."""
        with pytest.raises(ValidationError):
            SurveyResponseSubmitRequest(
                respostas=VALID_RESPOSTAS,
                texto_livre="x" * 2001,
                consentimento_texto_livre=True,
            )

    def test_missing_respostas_raises_422(self):
        """Ausência do campo obrigatório 'respostas' levanta ValidationError."""
        with pytest.raises(ValidationError):
            SurveyResponseSubmitRequest()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SurveyResponseSubmitResponse
# ---------------------------------------------------------------------------


class TestSurveyResponseSubmitResponse:
    def test_valid_response(self):
        """Resposta de submissão contém id, campaign_id e mensagem."""
        resp = SurveyResponseSubmitResponse(
            id=str(uuid.uuid4()),
            campaign_id=str(uuid.uuid4()),
            mensagem="Resposta registrada. Analytics será atualizado em breve.",
        )
        assert resp.id
        assert resp.campaign_id
        assert "Analytics" in resp.mensagem


# ---------------------------------------------------------------------------
# SurveyResponseListItem — Anonimização
# ---------------------------------------------------------------------------


class TestSurveyResponseListItem:
    def test_list_item_does_not_expose_pii_fields(self):
        """SurveyResponseListItem não possui campos texto_livre, email ou respostas."""
        fields = SurveyResponseListItem.model_fields
        # Verificar que dados identificáveis não fazem parte do schema
        assert "texto_livre" not in fields, "texto_livre não deve ser exposto"
        assert "email" not in fields, "email não deve ser exposto"
        assert "respostas" not in fields, "respostas brutas não devem ser expostas"

    def test_list_item_has_required_anonymous_fields(self):
        """SurveyResponseListItem possui os campos anonimizados obrigatórios."""
        fields = SurveyResponseListItem.model_fields
        assert "id" in fields
        assert "campaign_id" in fields
        assert "anonimizado" in fields
        assert "created_at" in fields

    def test_list_item_sentimento_is_optional(self):
        """Campo sentimento é opcional em SurveyResponseListItem."""
        item = SurveyResponseListItem(
            id=uuid.uuid4(),
            campaign_id=uuid.uuid4(),
            anonimizado=True,
            sentimento=None,
            created_at=datetime.now(tz=timezone.utc),
        )
        assert item.sentimento is None

    def test_list_item_from_mock_object(self):
        """SurveyResponseListItem pode ser construído com dados típicos."""
        item = SurveyResponseListItem(
            id=uuid.uuid4(),
            campaign_id=uuid.uuid4(),
            anonimizado=True,
            sentimento="positivo",
            created_at=datetime.now(tz=timezone.utc),
        )
        assert item.anonimizado is True
        assert item.sentimento == "positivo"


# ---------------------------------------------------------------------------
# SurveyResponseListResponse — Paginação
# ---------------------------------------------------------------------------


class TestSurveyResponseListResponse:
    def test_list_response_has_items_and_pagination(self):
        """Resposta de listagem possui items e pagination."""
        resp = SurveyResponseListResponse(
            items=[],
            pagination=SurveyResponsePaginationMeta(
                page=1,
                page_size=20,
                total=0,
                pages=0,
            ),
        )
        assert resp.items == []
        assert resp.pagination.page == 1
        assert resp.pagination.page_size == 20
        assert resp.pagination.total == 0

    def test_pagination_meta_page_size_max_100(self):
        """SurveyResponsePaginationMeta rejeita page_size > 100."""
        with pytest.raises(ValidationError):
            SurveyResponsePaginationMeta(
                page=1,
                page_size=101,
                total=0,
                pages=0,
            )

    def test_pagination_meta_valid(self):
        """SurveyResponsePaginationMeta aceita valores válidos."""
        meta = SurveyResponsePaginationMeta(
            page=3,
            page_size=50,
            total=150,
            pages=3,
        )
        assert meta.page == 3
        assert meta.page_size == 50
        assert meta.total == 150
        assert meta.pages == 3
