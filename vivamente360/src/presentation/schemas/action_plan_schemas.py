"""Schemas Pydantic para o módulo de Plano de Ação.

Regra R1: type hints completos em todos os campos e métodos.
Regra R4: respostas de listagem sempre incluem PaginationMeta e resumo por status.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ActionPlanCreate(BaseModel):
    """Payload para criação de um novo Plano de Ação."""

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Título descritivo do plano de ação.",
    )
    descricao: str = Field(
        ...,
        min_length=10,
        description="Descrição detalhada das ações planejadas.",
    )
    nivel_risco: NivelRisco = Field(
        ...,
        description=(
            "Nível de risco da dimensão alvo. "
            "Valores: 'aceitavel', 'moderado', 'importante', 'critico'."
        ),
    )
    prazo: date = Field(
        ...,
        description="Data limite para conclusão do plano (formato ISO 8601: YYYY-MM-DD).",
    )
    dimensao: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Dimensão HSE-IT vinculada (ex: 'demandas', 'controle'). Opcional.",
    )
    unidade_id: Optional[UUID] = Field(
        default=None,
        description="UUID da unidade organizacional alvo. Opcional.",
    )
    setor_id: Optional[UUID] = Field(
        default=None,
        description="UUID do setor alvo. Opcional.",
    )
    responsavel_id: Optional[UUID] = Field(
        default=None,
        description="UUID do responsável interno pelo plano. Opcional.",
    )
    responsavel_externo: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Nome do responsável externo ao sistema. Opcional.",
    )


class ActionPlanUpdate(BaseModel):
    """Payload parcial para atualização de um Plano de Ação (PATCH).

    Todos os campos são opcionais — apenas os informados serão atualizados.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=500,
        description="Novo título do plano.",
    )
    descricao: Optional[str] = Field(
        default=None,
        min_length=10,
        description="Nova descrição do plano.",
    )
    dimensao: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Nova dimensão HSE-IT vinculada.",
    )
    unidade_id: Optional[UUID] = Field(
        default=None,
        description="Novo UUID da unidade organizacional alvo.",
    )
    setor_id: Optional[UUID] = Field(
        default=None,
        description="Novo UUID do setor alvo.",
    )
    responsavel_id: Optional[UUID] = Field(
        default=None,
        description="Novo UUID do responsável interno.",
    )
    responsavel_externo: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Novo nome do responsável externo.",
    )
    nivel_risco: Optional[NivelRisco] = Field(
        default=None,
        description="Novo nível de risco.",
    )
    prazo: Optional[date] = Field(
        default=None,
        description="Nova data limite para conclusão.",
    )


class ActionPlanStatusUpdate(BaseModel):
    """Payload para transição de status de um Plano de Ação.

    Regra: status='concluido' seta concluido_em automaticamente no service.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    status: ActionPlanStatus = Field(
        ...,
        description=(
            "Novo status do plano. "
            "Valores: 'pendente', 'em_andamento', 'concluido', 'cancelado'."
        ),
    )
    observacao: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Observação opcional registrada junto à transição de status.",
    )


class ActionPlanEvidenciaCreate(BaseModel):
    """Metadados de arquivo para registrar uma evidência de plano de ação.

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
# Response schemas
# ---------------------------------------------------------------------------


class ActionPlanEvidenciaResponse(BaseModel):
    """Metadados de uma evidência de plano de ação (file_asset).

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


class ActionPlanResponse(BaseModel):
    """Representação completa de um Plano de Ação.

    Inclui todos os campos do plano. Evidências são retornadas apenas
    no endpoint de detalhe (GET /{plan_id}).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    company_id: UUID
    titulo: str
    descricao: str
    dimensao: Optional[str]
    unidade_id: Optional[UUID]
    setor_id: Optional[UUID]
    responsavel_id: Optional[UUID]
    responsavel_externo: Optional[str]
    nivel_risco: NivelRisco
    status: ActionPlanStatus
    prazo: date
    concluido_em: Optional[datetime]
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ActionPlanDetailResponse(BaseModel):
    """Resposta do endpoint GET /action-plans/{campaign_id}/{plan_id}.

    Inclui o plano completo com a lista de evidências vinculadas.
    """

    plan: ActionPlanResponse
    evidencias: list[ActionPlanEvidenciaResponse]


# ---------------------------------------------------------------------------
# Response schemas — Resumo e Paginação
# ---------------------------------------------------------------------------


class ActionPlanResumo(BaseModel):
    """Resumo dos planos de ação de uma campanha por status.

    Sempre calculado sobre o total da campanha, independente de filtros aplicados.
    """

    total: int = Field(..., description="Total de planos na campanha.")
    por_status: dict[str, int] = Field(
        ...,
        description=(
            "Contagem de planos agrupada por status. "
            "Chaves: 'pendente', 'em_andamento', 'concluido', 'cancelado'."
        ),
    )


class ActionPlanPaginationMeta(BaseModel):
    """Metadados de paginação para listagens de planos de ação."""

    page: int
    page_size: int
    total: int
    pages: int


class ActionPlanListResponse(BaseModel):
    """Resposta do endpoint GET /action-plans/{campaign_id}.

    Contém os planos filtrados e paginados, o resumo global da campanha
    por status e os metadados de paginação.
    """

    items: list[ActionPlanResponse]
    resumo: ActionPlanResumo
    pagination: ActionPlanPaginationMeta
