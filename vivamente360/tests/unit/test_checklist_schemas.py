"""Testes unitários dos Schemas de Checklist — Blueprint 09.

Cobre:
    - ToggleItemRequest: validação de campos
    - CreateEvidenciaRequest: validação de campos obrigatórios e limites
    - ChecklistItemResponse: serialização correta
    - ChecklistListResponse: estrutura paginada
    - ChecklistProgresso: cálculo de percentual
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError


class TestToggleItemRequest:
    def test_toggle_item_concluido_true(self):
        """Payload válido com concluido=True é aceito."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        req = ToggleItemRequest(concluido=True)
        assert req.concluido is True
        assert req.observacao is None

    def test_toggle_item_concluido_false(self):
        """Payload válido com concluido=False é aceito."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        req = ToggleItemRequest(concluido=False)
        assert req.concluido is False

    def test_toggle_item_with_observacao(self):
        """Campo observacao opcional é aceito."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        req = ToggleItemRequest(concluido=True, observacao="Reunião realizada")
        assert req.observacao == "Reunião realizada"

    def test_toggle_item_observacao_too_long_raises_validation_error(self):
        """Observação com mais de 2000 chars levanta ValidationError."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        with pytest.raises(ValidationError):
            ToggleItemRequest(concluido=True, observacao="x" * 2001)

    def test_toggle_item_missing_concluido_raises_validation_error(self):
        """Campo concluido é obrigatório."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        with pytest.raises(ValidationError):
            ToggleItemRequest()

    def test_toggle_item_strips_whitespace(self):
        """Whitespace da observação é removido."""
        from src.presentation.schemas.checklist_schemas import ToggleItemRequest

        req = ToggleItemRequest(concluido=True, observacao="  Texto  ")
        assert req.observacao == "Texto"


class TestCreateEvidenciaRequest:
    def test_valid_evidencia_request(self):
        """Payload válido de evidência é aceito."""
        from src.presentation.schemas.checklist_schemas import CreateEvidenciaRequest

        req = CreateEvidenciaRequest(
            nome_original="laudo.pdf",
            tamanho_bytes=1024,
            content_type="application/pdf",
            storage_key="company/checklist/uuid/laudo.pdf",
        )
        assert req.nome_original == "laudo.pdf"
        assert req.tamanho_bytes == 1024

    def test_evidencia_nome_too_long_raises_error(self):
        """Nome com mais de 500 chars levanta ValidationError."""
        from src.presentation.schemas.checklist_schemas import CreateEvidenciaRequest

        with pytest.raises(ValidationError):
            CreateEvidenciaRequest(
                nome_original="n" * 501,
                tamanho_bytes=1024,
                content_type="application/pdf",
                storage_key="key",
            )

    def test_evidencia_tamanho_zero_raises_error(self):
        """Tamanho <= 0 levanta ValidationError (gt=0)."""
        from src.presentation.schemas.checklist_schemas import CreateEvidenciaRequest

        with pytest.raises(ValidationError):
            CreateEvidenciaRequest(
                nome_original="arquivo.pdf",
                tamanho_bytes=0,
                content_type="application/pdf",
                storage_key="key",
            )

    def test_evidencia_missing_required_fields_raises_error(self):
        """Campos obrigatórios ausentes levantam ValidationError."""
        from src.presentation.schemas.checklist_schemas import CreateEvidenciaRequest

        with pytest.raises(ValidationError):
            CreateEvidenciaRequest()


class TestChecklistItemResponse:
    def test_item_response_from_attributes(self):
        """ChecklistItemResponse é populado corretamente de um objeto ORM-like."""
        from src.presentation.schemas.checklist_schemas import ChecklistItemResponse

        item_id = uuid.uuid4()
        template_id = uuid.uuid4()
        company_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        campaign_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

        response = ChecklistItemResponse(
            id=item_id,
            campaign_id=campaign_id,
            template_id=template_id,
            company_id=company_id,
            codigo="NR1.01",
            descricao="Avaliar riscos psicossociais",
            categoria="avaliacao",
            obrigatorio=True,
            prazo_dias=30,
            ordem=1,
            concluido=False,
            concluido_em=None,
            concluido_por=None,
            observacao=None,
            prazo=None,
            created_at=datetime.now(tz=timezone.utc),
        )

        assert response.id == item_id
        assert response.codigo == "NR1.01"
        assert response.concluido is False


class TestChecklistProgresso:
    def test_progresso_full_completion(self):
        """Progresso 100% é representado corretamente."""
        from src.presentation.schemas.checklist_schemas import ChecklistProgresso

        progresso = ChecklistProgresso(total=10, concluidos=10, percentual=100.0)
        assert progresso.percentual == 100.0

    def test_progresso_no_items(self):
        """Checklist sem itens tem percentual 0."""
        from src.presentation.schemas.checklist_schemas import ChecklistProgresso

        progresso = ChecklistProgresso(total=0, concluidos=0, percentual=0.0)
        assert progresso.percentual == 0.0

    def test_progresso_partial(self):
        """Progresso parcial é representado corretamente."""
        from src.presentation.schemas.checklist_schemas import ChecklistProgresso

        progresso = ChecklistProgresso(total=10, concluidos=5, percentual=50.0)
        assert progresso.concluidos == 5


class TestChecklistListResponse:
    def test_checklist_list_response_structure(self):
        """ChecklistListResponse contém items, progresso e pagination."""
        from src.presentation.schemas.checklist_schemas import (
            ChecklistItemResponse,
            ChecklistListResponse,
            ChecklistPaginationMeta,
            ChecklistProgresso,
        )

        response = ChecklistListResponse(
            items=[],
            progresso=ChecklistProgresso(total=0, concluidos=0, percentual=0.0),
            pagination=ChecklistPaginationMeta(page=1, page_size=50, total=0, pages=0),
        )

        assert response.items == []
        assert response.progresso.total == 0
        assert response.pagination.page == 1
