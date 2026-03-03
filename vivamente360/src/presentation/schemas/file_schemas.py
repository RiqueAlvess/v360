from uuid import UUID

from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """Resposta do endpoint POST /files/upload."""

    file_id: UUID = Field(description="UUID do registro file_asset criado")
    filename: str = Field(description="Nome original do arquivo enviado")
    size_bytes: int = Field(description="Tamanho do arquivo em bytes")
    signed_url: str = Field(description="URL pré-assinada para download (válida por 1h)")


class SignedUrlResponse(BaseModel):
    """Resposta do endpoint GET /files/{file_id}/url."""

    signed_url: str = Field(description="URL pré-assinada para download (válida por 1h)")
