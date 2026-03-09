"""Testes unitários dos Schemas de Whistleblower — Blueprint 12.

Cobre:
    - WhistleblowerSubmitRequest: validações de campo (descricao min, anonimato)
    - WhistleblowerSubmitResponse: report_token presente, nunca token_hash
    - WhistleblowerReportResponse: não expõe token_hash nem user_id identificável
    - WhistleblowerConsultaResponse: apenas status e resposta_institucional
    - WhistleblowerResponderRequest: validações de campo
    - WhistleblowerListResponse: estrutura paginada
    - Regra de anonimato: schemas de resposta NÃO expõem dados identificáveis
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.domain.enums.whistleblower_categoria import WhistleblowerCategoria
from src.domain.enums.whistleblower_status import WhistleblowerStatus


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class TestWhistleblowerSubmitRequest:
    def test_valid_request_accepted(self):
        """Payload válido com categoria e descrição é aceito."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        req = WhistleblowerSubmitRequest(
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="Relato detalhado sobre assédio moral no ambiente de trabalho",
        )

        assert req.categoria == WhistleblowerCategoria.ASSEDIO_MORAL
        assert req.nome_opcional is None  # Anônimo por padrão

    def test_descricao_too_short_raises_validation_error(self):
        """Descrição com menos de 20 chars levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        with pytest.raises(ValidationError):
            WhistleblowerSubmitRequest(
                categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
                descricao="Curto",  # < min_length=20
            )

    def test_descricao_too_long_raises_validation_error(self):
        """Descrição acima de 10000 chars levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        with pytest.raises(ValidationError):
            WhistleblowerSubmitRequest(
                categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
                descricao="x" * 10_001,
            )

    def test_with_nome_opcional_accepted(self):
        """Payload com nome_opcional (anonimo=False) é aceito."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        req = WhistleblowerSubmitRequest(
            categoria=WhistleblowerCategoria.CORRUPCAO,
            descricao="Relato detalhado sobre corrupção no setor financeiro",
            nome_opcional="Maria Souza",
        )

        assert req.nome_opcional == "Maria Souza"

    def test_nome_opcional_too_long_raises_error(self):
        """Nome com mais de 255 chars levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        with pytest.raises(ValidationError):
            WhistleblowerSubmitRequest(
                categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
                descricao="Relato válido com mais de 20 caracteres para passar",
                nome_opcional="x" * 256,
            )

    def test_invalid_categoria_raises_validation_error(self):
        """Categoria inválida levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        with pytest.raises(ValidationError):
            WhistleblowerSubmitRequest(
                categoria="categoria_inexistente",
                descricao="Relato válido com mais de 20 caracteres",
            )

    def test_strips_whitespace_from_descricao(self):
        """Whitespace da descrição é removido."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitRequest

        req = WhistleblowerSubmitRequest(
            categoria=WhistleblowerCategoria.ASSEDIO_MORAL,
            descricao="  Relato detalhado com espaços em volta  ",
        )

        assert not req.descricao.startswith(" ")
        assert not req.descricao.endswith(" ")


class TestWhistleblowerSubmitResponse:
    def test_submit_response_has_report_token(self):
        """WhistleblowerSubmitResponse expõe report_token."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitResponse

        response = WhistleblowerSubmitResponse(report_token="token_abc123_urlsafe_43chars_xxxxxxxxxxx")

        assert response.report_token == "token_abc123_urlsafe_43chars_xxxxxxxxxxx"
        assert response.message  # Mensagem de confirmação presente

    def test_submit_response_fields_do_not_include_token_hash(self):
        """WhistleblowerSubmitResponse NÃO expõe token_hash."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitResponse

        response = WhistleblowerSubmitResponse(report_token="token_aqui")

        # Schema não deve ter campo token_hash
        assert not hasattr(response, "token_hash")

    def test_submit_response_fields_do_not_include_user_id(self):
        """WhistleblowerSubmitResponse NÃO expõe user_id."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerSubmitResponse

        response = WhistleblowerSubmitResponse(report_token="token_aqui")

        # Schema não deve ter campo user_id
        assert not hasattr(response, "user_id")


class TestWhistleblowerReportResponse:
    def test_report_response_valid(self):
        """WhistleblowerReportResponse é válido com todos os campos obrigatórios."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerReportResponse

        response = WhistleblowerReportResponse(
            id=uuid.uuid4(),
            company_id=COMPANY_ID,
            categoria="assedio_moral",
            descricao="Relato detalhado sobre assédio moral",
            anonimo=True,
            nome_opcional=None,
            status="recebido",
            resposta_institucional=None,
            respondido_por=None,
            respondido_em=None,
            created_at=datetime.now(tz=timezone.utc),
        )

        assert response.anonimo is True
        assert response.nome_opcional is None

    def test_report_response_does_not_expose_token_hash(self):
        """WhistleblowerReportResponse NÃO expõe token_hash."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerReportResponse

        response = WhistleblowerReportResponse(
            id=uuid.uuid4(),
            company_id=COMPANY_ID,
            categoria="assedio_moral",
            descricao="Relato de teste com identificação",
            anonimo=False,
            nome_opcional="Denunciante",
            status="recebido",
            resposta_institucional=None,
            respondido_por=None,
            respondido_em=None,
            created_at=datetime.now(tz=timezone.utc),
        )

        # token_hash nunca é exposto no schema de response
        assert not hasattr(response, "token_hash")

    def test_anonymous_report_has_no_nome(self):
        """Relato anônimo não expõe nome_opcional."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerReportResponse

        response = WhistleblowerReportResponse(
            id=uuid.uuid4(),
            company_id=COMPANY_ID,
            categoria="assedio_moral",
            descricao="Relato anônimo aqui",
            anonimo=True,
            nome_opcional=None,  # Anônimo → sem nome
            status="recebido",
            resposta_institucional=None,
            respondido_por=None,
            respondido_em=None,
            created_at=datetime.now(tz=timezone.utc),
        )

        assert response.nome_opcional is None


class TestWhistleblowerConsultaResponse:
    def test_consulta_response_with_status_only(self):
        """WhistleblowerConsultaResponse com apenas status é válido."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerConsultaResponse

        response = WhistleblowerConsultaResponse(
            status="recebido",
            resposta_institucional=None,
            respondido_em=None,
        )

        assert response.status == "recebido"
        assert response.resposta_institucional is None

    def test_consulta_response_with_resposta(self):
        """WhistleblowerConsultaResponse com resposta institucional é válido."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerConsultaResponse

        now = datetime.now(tz=timezone.utc)
        response = WhistleblowerConsultaResponse(
            status="concluido",
            resposta_institucional="Caso encerrado com as devidas providências.",
            respondido_em=now,
        )

        assert response.resposta_institucional is not None
        assert response.respondido_em == now

    def test_consulta_response_does_not_expose_internal_data(self):
        """WhistleblowerConsultaResponse NÃO expõe campos internos."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerConsultaResponse

        response = WhistleblowerConsultaResponse(
            status="em_analise",
            resposta_institucional=None,
            respondido_em=None,
        )

        # Campos internos jamais aparecem na resposta pública
        assert not hasattr(response, "token_hash")
        assert not hasattr(response, "company_id")
        assert not hasattr(response, "respondido_por")


class TestWhistleblowerResponderRequest:
    def test_responder_request_valid(self):
        """WhistleblowerResponderRequest válido é aceito."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerResponderRequest

        req = WhistleblowerResponderRequest(
            resposta_institucional="Estamos investigando o ocorrido e tomaremos as medidas cabíveis.",
            status=WhistleblowerStatus.EM_ANALISE,
        )

        assert req.status == WhistleblowerStatus.EM_ANALISE

    def test_responder_request_too_short_raises_error(self):
        """Resposta com menos de 10 chars levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerResponderRequest

        with pytest.raises(ValidationError):
            WhistleblowerResponderRequest(
                resposta_institucional="Curto",  # < min_length=10
                status=WhistleblowerStatus.EM_ANALISE,
            )

    def test_responder_request_invalid_status_raises_error(self):
        """Status inválido levanta ValidationError."""
        from src.presentation.schemas.whistleblower_schemas import WhistleblowerResponderRequest

        with pytest.raises(ValidationError):
            WhistleblowerResponderRequest(
                resposta_institucional="Resposta válida aqui com mais de 10 chars",
                status="status_invalido",
            )


class TestWhistleblowerListResponse:
    def test_list_response_structure(self):
        """WhistleblowerListResponse contém items e pagination."""
        from src.presentation.schemas.whistleblower_schemas import (
            PaginationMeta,
            WhistleblowerListResponse,
        )

        response = WhistleblowerListResponse(
            items=[],
            pagination=PaginationMeta(page=1, page_size=20, total=0, pages=0),
        )

        assert response.items == []
        assert response.pagination.total == 0
