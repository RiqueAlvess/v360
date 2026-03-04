"""Schemas Pydantic do módulo de File Assets.

Regra R1: Type hints completos em todos os campos.
Regra R2: Schemas apenas validam/serializam — nenhuma lógica de negócio.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FileAssetResponse(BaseModel):
    """Resposta com metadados de um arquivo uploadado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    contexto: str
    referencia_id: Optional[uuid.UUID] = None
    nome_original: str
    tamanho_bytes: int
    content_type: str
    storage_key: str
    created_by: Optional[uuid.UUID] = None
    created_at: datetime


class FileSignedUrlResponse(BaseModel):
    """Resposta com URL assinada temporária para download."""

    file_id: uuid.UUID
    nome_original: str
    content_type: str
    tamanho_bytes: int
    url: str
    expires_in_seconds: int


class FileListResponse(BaseModel):
    """Resposta paginada da listagem de arquivos."""

    items: list[FileAssetResponse]
    pagination: "FilePaginationMeta"


class FilePaginationMeta(BaseModel):
    """Metadados de paginação para listagem de arquivos."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    pages: int = Field(ge=0)


class FileDeleteResponse(BaseModel):
    """Confirmação de exclusão lógica de arquivo."""

    file_id: uuid.UUID
    deletado: bool
    mensagem: str
