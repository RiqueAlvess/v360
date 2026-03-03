"""Schemas Pydantic para o módulo de Checklist NR-1.

Regra R1: type hints completos em todos os campos e métodos.
Regra R4: respostas de listagem sempre incluem PaginationMeta.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ToggleItemRequest(BaseModel):
    """Payload para alternar o status de conclusão de um item do checklist."""

    model_config = ConfigDict(str_strip_whitespace=True)

    concluido: bool = Field(
        ...,
        description="Novo estado de conclusão do item.",
    )
    observacao: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Observação opcional registrada pelo gestor ao concluir ou reabrir.",
    )


class CreateEvidenciaRequest(BaseModel):
    """Metadados de arquivo para registrar uma evidência de checklist.

    O upload físico do arquivo para o Cloudflare R2 é tratado pelo Módulo 01
    (File Management). Este schema registra apenas os metadados do asset.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    nome_original: str = Field(
        ...,
        max_length=500,
        description="Nome original do arquivo conforme enviado pelo usuário.",
    )
    tamanho_bytes: int = Field(
        ...,
        gt=0,
        description="Tamanho do arquivo em bytes.",
    )
    content_type: str = Field(
        ...,
        max_length=200,
        description="MIME type do arquivo (ex: 'application/pdf', 'image/png').",
    )
    storage_key: str = Field(
        ...,
        max_length=500,
        description="Chave do arquivo no Cloudflare R2 após upload.",
    )


# ---------------------------------------------------------------------------
# Response schemas — Templates
# ---------------------------------------------------------------------------


class ChecklistTemplateResponse(BaseModel):
    """Representação de um template canônico NR-1."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    descricao: str
    categoria: str
    obrigatorio: bool
    prazo_dias: Optional[int]
    ordem: int


# ---------------------------------------------------------------------------
# Response schemas — Itens
# ---------------------------------------------------------------------------


class ChecklistItemResponse(BaseModel):
    """Representação completa de um item de checklist vinculado a uma campanha.

    Inclui os campos do template (codigo, descricao, categoria, obrigatorio,
    prazo_dias, ordem) desnormalizados para facilitar o consumo pelo cliente
    sem necessidade de joins adicionais.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    template_id: UUID
    company_id: UUID

    # Campos desnormalizados do template
    codigo: str
    descricao: str
    categoria: str
    obrigatorio: bool
    prazo_dias: Optional[int]
    ordem: int

    # Estado do item
    concluido: bool
    concluido_em: Optional[datetime]
    concluido_por: Optional[UUID]
    observacao: Optional[str]
    prazo: Optional[date]
    created_at: datetime


# ---------------------------------------------------------------------------
# Response schemas — Progresso
# ---------------------------------------------------------------------------


class ChecklistProgresso(BaseModel):
    """Indicador de progresso do checklist de uma campanha."""

    total: int = Field(..., description="Total de itens no checklist da campanha.")
    concluidos: int = Field(..., description="Quantidade de itens marcados como concluídos.")
    percentual: float = Field(
        ...,
        description="Percentual de conclusão (0.0 a 100.0), arredondado a 1 casa decimal.",
    )


# ---------------------------------------------------------------------------
# Response schemas — Listagem paginada
# ---------------------------------------------------------------------------


class ChecklistPaginationMeta(BaseModel):
    """Metadados de paginação para listagens de checklist."""

    page: int
    page_size: int
    total: int
    pages: int


class ChecklistListResponse(BaseModel):
    """Resposta do endpoint GET /checklists/{campaign_id}.

    Contém os itens do checklist filtrados e paginados, o indicador de
    progresso global da campanha e os metadados de paginação.
    """

    items: list[ChecklistItemResponse]
    progresso: ChecklistProgresso
    pagination: ChecklistPaginationMeta


# ---------------------------------------------------------------------------
# Response schemas — Evidências
# ---------------------------------------------------------------------------


class EvidenciaResponse(BaseModel):
    """Metadados de uma evidência de checklist (file_asset).

    O campo storage_key NÃO é exposto — o acesso ao arquivo físico se dá
    apenas via signed URLs geradas pelo Módulo 01 (File Management).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome_original: str
    content_type: str
    tamanho_bytes: int
    created_by: Optional[UUID]
    created_at: datetime


# ---------------------------------------------------------------------------
# Response schemas — Campaigns (usado por CampaignService e CampaignRouter)
# ---------------------------------------------------------------------------


class CampaignCreateRequest(BaseModel):
    """Payload para criação de uma nova campanha.

    A criação de uma campanha dispara automaticamente a geração de todos
    os checklist_items a partir dos checklist_templates ativos (hook no CampaignService).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    nome: str = Field(..., min_length=3, max_length=255, description="Nome da campanha.")
    data_inicio: date = Field(..., description="Data de início da campanha.")
    data_fim: date = Field(..., description="Data de encerramento da campanha.")


class CampaignResponse(BaseModel):
    """Representação de uma campanha de avaliação psicossocial."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    nome: str
    status: str
    data_inicio: date
    data_fim: date
    created_at: datetime
    updated_at: datetime


class CampaignListResponse(BaseModel):
    """Resposta paginada do endpoint GET /campaigns."""

    items: list[CampaignResponse]
    pagination: ChecklistPaginationMeta
