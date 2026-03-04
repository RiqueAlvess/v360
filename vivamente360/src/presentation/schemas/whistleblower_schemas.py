"""Schemas Pydantic para o Canal de Denúncias Anônimo — Módulo 07.

Regra R1: type hints completos em todos os campos.
Regra R4: respostas de listagem sempre incluem PaginationMeta.

ANONIMATO:
    - WhistleblowerSubmitResponse expõe report_token APENAS UMA VEZ.
    - Nenhum schema de resposta admin expõe dados identificáveis do denunciante
      além do nome_opcional (preenchido somente se anonimo=False).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums.whistleblower_categoria import WhistleblowerCategoria
from src.domain.enums.whistleblower_status import WhistleblowerStatus


# ---------------------------------------------------------------------------
# Request schemas — Público (sem autenticação)
# ---------------------------------------------------------------------------


class WhistleblowerSubmitRequest(BaseModel):
    """Payload para submissão de um relato anônimo no canal de denúncias.

    O campo nome_opcional só é enviado pelo denunciante que opta por
    se identificar voluntariamente (anonimo=False).
    Sem autenticação. Sem IP. Sem sessão.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    categoria: WhistleblowerCategoria = Field(
        ...,
        description="Categoria da denúncia.",
    )
    descricao: str = Field(
        ...,
        min_length=20,
        max_length=10_000,
        description="Descrição detalhada do relato.",
    )
    nome_opcional: Optional[str] = Field(
        default=None,
        max_length=255,
        description=(
            "Nome do denunciante — preenchido APENAS se optar por se identificar. "
            "Quando ausente, o relato é tratado como anônimo."
        ),
    )


# ---------------------------------------------------------------------------
# Request schemas — Admin (autenticado)
# ---------------------------------------------------------------------------


class WhistleblowerResponderRequest(BaseModel):
    """Payload para registrar a resposta institucional a um relato."""

    model_config = ConfigDict(str_strip_whitespace=True)

    resposta_institucional: str = Field(
        ...,
        min_length=10,
        max_length=10_000,
        description="Texto da resposta oficial da empresa ao relato.",
    )
    status: WhistleblowerStatus = Field(
        ...,
        description="Novo status do relato após a resposta (em_analise, concluido, arquivado).",
    )


# ---------------------------------------------------------------------------
# Response schemas — Público
# ---------------------------------------------------------------------------


class WhistleblowerSubmitResponse(BaseModel):
    """Resposta ao submit de um novo relato.

    IMPORTANTE: report_token é exibido APENAS UMA VEZ. O banco armazena
    apenas o SHA-256 (token_hash). O denunciante deve guardar este token
    para acompanhar a resposta institucional via /consulta.
    """

    report_token: str = Field(
        ...,
        description=(
            "Token único para acompanhamento do relato. "
            "Exibido APENAS UMA VEZ — guarde-o com segurança. "
            "Use em GET /denuncia/{slug}/consulta?token={report_token}."
        ),
    )
    message: str = Field(
        default=(
            "Seu relato foi recebido com segurança. Guarde o token acima "
            "para acompanhar a resposta institucional."
        ),
        description="Mensagem de confirmação ao denunciante.",
    )


class WhistleblowerConsultaResponse(BaseModel):
    """Resposta da consulta pública pelo denunciante via token de acompanhamento.

    Expõe apenas o status e a resposta institucional — sem dados internos.
    """

    status: str = Field(..., description="Status atual do relato.")
    resposta_institucional: Optional[str] = Field(
        default=None,
        description="Resposta oficial da empresa, quando disponível.",
    )
    respondido_em: Optional[datetime] = Field(
        default=None,
        description="Data e hora em que a resposta foi registrada.",
    )


# ---------------------------------------------------------------------------
# Response schemas — Admin
# ---------------------------------------------------------------------------


class WhistleblowerReportResponse(BaseModel):
    """Representação completa de um relato para moderadores e compliance.

    NÃO expõe token_hash — apenas admins com acesso ao banco têm este dado.
    Se anonimo=True, nome_opcional é None — sem dados identificáveis.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    categoria: str
    descricao: str
    anonimo: bool
    nome_opcional: Optional[str]
    status: str
    resposta_institucional: Optional[str]
    respondido_por: Optional[UUID]
    respondido_em: Optional[datetime]
    created_at: datetime


class PaginationMeta(BaseModel):
    """Metadados de paginação — padrão de todos os endpoints de listagem (Regra R4)."""

    page: int
    page_size: int
    total: int
    pages: int


class WhistleblowerListResponse(BaseModel):
    """Resposta paginada do endpoint GET /admin/whistleblower."""

    items: list[WhistleblowerReportResponse]
    pagination: PaginationMeta
