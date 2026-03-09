"""Testes unitários do R2StorageAdapter.

Cobre as validações de segurança críticas:
    - Rejeição por tamanho (StorageSizeLimitExceeded)
    - Rejeição por content-type não permitido (StorageContentTypeNotAllowed)
    - Rejeição por magic bytes divergentes (StorageMagicBytesMismatch)
    - Aceitação de tipos válidos com magic bytes corretos
"""
import pytest

from src.infrastructure.storage.r2_adapter import (
    ALLOWED_CONTENT_TYPES,
    R2StorageAdapter,
    StorageContentTypeNotAllowed,
    StorageMagicBytesMismatch,
    StorageSizeLimitExceeded,
    build_storage_key,
)


@pytest.fixture
def adapter():
    """R2StorageAdapter com limite reduzido para facilitar testes."""
    return R2StorageAdapter(
        bucket_name="test-bucket",
        endpoint_url="https://test.r2.example.com",
        access_key_id="test_key",
        secret_access_key="test_secret",
        max_file_size=5 * 1024 * 1024,  # 5 MB para testes
    )


# Magic bytes de exemplo para cada tipo
JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 20
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
PDF_MAGIC = b"%PDF-1.4\n" + b"\x00" * 20
ZIP_MAGIC = b"PK\x03\x04" + b"\x00" * 20


# ---------------------------------------------------------------------------
# _validate() — validações de segurança
# ---------------------------------------------------------------------------


class TestR2AdapterValidation:
    def test_validate_exceeds_size_limit_raises_error(self, adapter):
        """Arquivo acima do limite levanta StorageSizeLimitExceeded."""
        oversized_data = b"\xff\xd8\xff" + b"\x00" * (6 * 1024 * 1024)  # 6 MB > 5 MB limit

        with pytest.raises(StorageSizeLimitExceeded) as exc_info:
            adapter._validate(oversized_data, "image/jpeg")

        assert exc_info.value.size_bytes > exc_info.value.limit_bytes

    def test_validate_disallowed_content_type_raises_error(self, adapter):
        """Content-type fora da whitelist levanta StorageContentTypeNotAllowed."""
        with pytest.raises(StorageContentTypeNotAllowed) as exc_info:
            adapter._validate(b"\x00" * 100, "application/x-executable")

        assert "application/x-executable" in exc_info.value.content_type

    def test_validate_script_content_type_blocked(self, adapter):
        """Scripts JS/Python são bloqueados pela whitelist."""
        for blocked_type in ["text/javascript", "application/x-python", "text/x-php"]:
            with pytest.raises(StorageContentTypeNotAllowed):
                adapter._validate(b"\x00" * 100, blocked_type)

    def test_validate_magic_bytes_mismatch_raises_error(self, adapter):
        """Magic bytes divergentes levantam StorageMagicBytesMismatch."""
        # Dados com magic bytes de JPEG mas declarado como PDF
        jpeg_data = JPEG_MAGIC

        with pytest.raises(StorageMagicBytesMismatch) as exc_info:
            adapter._validate(jpeg_data, "application/pdf")

        assert exc_info.value.declared == "application/pdf"

    def test_validate_valid_jpeg_passes(self, adapter):
        """JPEG com magic bytes corretos e content-type correto passa."""
        adapter._validate(JPEG_MAGIC, "image/jpeg")  # Não deve levantar

    def test_validate_valid_png_passes(self, adapter):
        """PNG com magic bytes corretos passa."""
        adapter._validate(PNG_MAGIC, "image/png")

    def test_validate_valid_pdf_passes(self, adapter):
        """PDF com magic bytes corretos passa."""
        adapter._validate(PDF_MAGIC, "application/pdf")

    def test_validate_ooxml_via_zip_magic_passes(self, adapter):
        """DOCX/XLSX/PPTX (ZIP internamente) com magic bytes ZIP passa."""
        adapter._validate(
            ZIP_MAGIC,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_validate_zip_file_as_zip_passes(self, adapter):
        """ZIP com magic bytes ZIP e content-type zip passa."""
        adapter._validate(ZIP_MAGIC, "application/zip")

    def test_validate_empty_content_type_fallback(self, adapter):
        """Content-type com charset é normalizado antes da whitelist."""
        # image/jpeg;charset=utf-8 deve ser normalizado para image/jpeg
        adapter._validate(JPEG_MAGIC, "image/jpeg;charset=utf-8")

    def test_validate_short_data_skips_magic_check(self, adapter):
        """Dados com menos de 12 bytes ignoram a verificação de magic bytes."""
        # Não deve levantar StorageMagicBytesMismatch para dados curtos
        short_data = b"\x00" * 5  # < 12 bytes
        adapter._validate(short_data, "text/plain")


# ---------------------------------------------------------------------------
# build_storage_key()
# ---------------------------------------------------------------------------


class TestBuildStorageKey:
    def test_key_format_includes_company_contexto_file(self):
        """Chave inclui company_id, contexto e file_id."""
        key = build_storage_key(
            company_id="11111111-1111-1111-1111-111111111111",
            contexto="checklist_evidencia",
            file_id="44444444-4444-4444-4444-444444444444",
            filename="evidencia.pdf",
        )

        assert "11111111111111111111111111111111" in key.replace("-", "")
        assert "checklist_evidencia" in key
        assert "44444444444444444444444444444444" in key.replace("-", "")

    def test_key_sanitizes_dangerous_filename_chars(self):
        """Caracteres perigosos no filename são substituídos por underscore."""
        key = build_storage_key(
            company_id="11111111-1111-1111-1111-111111111111",
            contexto="plano_acao",
            file_id="44444444-4444-4444-4444-444444444444",
            filename="../../../etc/passwd",
        )

        assert ".." not in key
        assert "/" not in key.split("plano_acao/")[1]

    def test_key_limits_filename_length(self):
        """Nomes de arquivo muito longos são truncados."""
        long_filename = "a" * 500 + ".pdf"
        key = build_storage_key(
            company_id="11111111-1111-1111-1111-111111111111",
            contexto="checklist_evidencia",
            file_id="44444444-4444-4444-4444-444444444444",
            filename=long_filename,
        )

        # A parte do filename no key não deve exceder 200 chars
        filename_part = key.split("/")[-1]
        assert len(filename_part) <= 200
