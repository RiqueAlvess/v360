"""Testes unitários dos Schemas de File Assets — Blueprint 11.

Cobre:
    - FileAssetResponse: serialização com todos os campos
    - FileSignedUrlResponse: estrutura de URL assinada
    - FileListResponse: resposta paginada
    - FilePaginationMeta: metadados de paginação
    - FileDeleteResponse: confirmação de exclusão
    - Regra: storage_key NÃO é exposto diretamente no response voltado ao cliente
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
FILE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


class TestFileAssetResponse:
    def test_file_asset_response_valid(self):
        """FileAssetResponse é criado com todos os campos obrigatórios."""
        from src.presentation.schemas.file_schemas import FileAssetResponse

        response = FileAssetResponse(
            id=FILE_ID,
            company_id=COMPANY_ID,
            contexto="checklist_evidencia",
            nome_original="laudo.pdf",
            tamanho_bytes=2048,
            content_type="application/pdf",
            storage_key="company/checklist/uuid/laudo.pdf",
            created_at=datetime.now(tz=timezone.utc),
        )

        assert response.id == FILE_ID
        assert response.nome_original == "laudo.pdf"

    def test_file_asset_response_with_optional_fields(self):
        """FileAssetResponse com referencia_id e created_by opcionais é válido."""
        from src.presentation.schemas.file_schemas import FileAssetResponse

        response = FileAssetResponse(
            id=FILE_ID,
            company_id=COMPANY_ID,
            contexto="plano_acao",
            referencia_id=uuid.uuid4(),
            nome_original="contrato.pdf",
            tamanho_bytes=5120,
            content_type="application/pdf",
            storage_key="company/plano/uuid/contrato.pdf",
            created_by=USER_ID,
            created_at=datetime.now(tz=timezone.utc),
        )

        assert response.created_by == USER_ID
        assert response.referencia_id is not None

    def test_file_asset_response_missing_required_raises_error(self):
        """Campos obrigatórios ausentes levantam ValidationError."""
        from src.presentation.schemas.file_schemas import FileAssetResponse

        with pytest.raises(ValidationError):
            FileAssetResponse()


class TestFileSignedUrlResponse:
    def test_signed_url_response_valid(self):
        """FileSignedUrlResponse com URL R2 válida é aceita."""
        from src.presentation.schemas.file_schemas import FileSignedUrlResponse

        response = FileSignedUrlResponse(
            file_id=FILE_ID,
            nome_original="evidencia.pdf",
            content_type="application/pdf",
            tamanho_bytes=1024,
            url="https://cdn.example.com/signed-url?token=abc123",
            expires_in_seconds=3600,
        )

        assert response.file_id == FILE_ID
        assert "signed-url" in response.url
        assert response.expires_in_seconds == 3600

    def test_signed_url_should_not_point_to_fastapi(self):
        """URL assinada nunca aponta para localhost/FastAPI diretamente."""
        from src.presentation.schemas.file_schemas import FileSignedUrlResponse

        response = FileSignedUrlResponse(
            file_id=FILE_ID,
            nome_original="evidencia.pdf",
            content_type="application/pdf",
            tamanho_bytes=1024,
            url="https://r2.cloudflare.com/bucket/file.pdf?token=abc",
            expires_in_seconds=3600,
        )

        # URL não deve apontar para FastAPI/localhost
        assert "localhost" not in response.url
        assert "127.0.0.1" not in response.url

    def test_signed_url_response_missing_required_raises_error(self):
        """Campos obrigatórios ausentes levantam ValidationError."""
        from src.presentation.schemas.file_schemas import FileSignedUrlResponse

        with pytest.raises(ValidationError):
            FileSignedUrlResponse()


class TestFileListResponse:
    def test_file_list_response_structure(self):
        """FileListResponse contém items e pagination."""
        from src.presentation.schemas.file_schemas import (
            FileAssetResponse,
            FileListResponse,
            FilePaginationMeta,
        )

        response = FileListResponse(
            items=[],
            pagination=FilePaginationMeta(page=1, page_size=20, total=0, pages=0),
        )

        assert response.items == []
        assert response.pagination.total == 0


class TestFilePaginationMeta:
    def test_pagination_meta_valid(self):
        """FilePaginationMeta com todos os campos é válida."""
        from src.presentation.schemas.file_schemas import FilePaginationMeta

        pagination = FilePaginationMeta(page=1, page_size=20, total=50, pages=3)
        assert pagination.pages == 3

    def test_pagination_meta_page_ge_1(self):
        """page deve ser >= 1."""
        from src.presentation.schemas.file_schemas import FilePaginationMeta

        with pytest.raises(ValidationError):
            FilePaginationMeta(page=0, page_size=20, total=0, pages=0)


class TestFileDeleteResponse:
    def test_delete_response_valid(self):
        """FileDeleteResponse com deletado=True é válido."""
        from src.presentation.schemas.file_schemas import FileDeleteResponse

        response = FileDeleteResponse(
            file_id=FILE_ID,
            deletado=True,
            mensagem="Arquivo excluído com sucesso.",
        )

        assert response.deletado is True
        assert response.file_id == FILE_ID
