"""Modelo SQLAlchemy para análises de IA geradas via OpenRouter.

Tabela: ai_analyses
RLS: ativada — isolamento por company_id via SET LOCAL app.company_id

Campos-chave:
    - tipo: 'sentimento' | 'diagnostico' | 'recomendacoes'
    - status: 'pending' | 'processing' | 'completed' | 'failed'
    - resultado: JSONB com output estruturado validado via Pydantic no handler
    - prompt_versao: rastreia qual versão de prompt gerou o resultado
    - tokens_input / tokens_output: controle de custo por análise
"""
import uuid
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base

# Valores válidos para o campo tipo
_TIPO_VALUES: tuple[str, ...] = ("sentimento", "diagnostico", "recomendacoes")

# Valores válidos para o campo status
_STATUS_VALUES: tuple[str, ...] = ("pending", "processing", "completed", "failed")


class AiAnalysis(Base):
    """Registro de uma análise de IA para uma campanha/setor.

    Criada via POST /ai-analyses/request, populada assincronamente
    pelo RunAiAnalysisHandler após processamento no task_queue.
    """

    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL = análise geral da campanha (sem recorte por setor)
    setor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # NULL = análise de todas as dimensões HSE-IT simultaneamente
    dimensao: Mapped[Optional[str]] = mapped_column(
        sa.String(50),
        nullable=True,
    )
    # Tipo de análise: 'sentimento' | 'diagnostico' | 'recomendacoes'
    tipo: Mapped[str] = mapped_column(
        sa.String(30),
        nullable=False,
    )
    # Status do ciclo de vida da análise
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    # Modelo efetivamente utilizado (registrado após conclusão)
    model_usado: Mapped[Optional[str]] = mapped_column(
        sa.String(100),
        nullable=True,
    )
    # Contadores de tokens para controle de custo
    tokens_input: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    tokens_output: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        nullable=True,
    )
    # Saída estruturada da IA — validada via Pydantic antes de persistir
    resultado: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    # Mensagem de erro (apenas quando status='failed')
    erro: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    # Versão do prompt utilizado — permite rastrear impacto de mudanças de prompt
    prompt_versao: Mapped[Optional[str]] = mapped_column(
        sa.String(20),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.CheckConstraint(
            f"tipo IN {_TIPO_VALUES}",
            name="ck_ai_analyses_tipo",
        ),
        sa.CheckConstraint(
            f"status IN {_STATUS_VALUES}",
            name="ck_ai_analyses_status",
        ),
        # Índice composto para listar análises por campanha ordenadas por data
        sa.Index("ix_ai_analyses_campaign_created", "campaign_id", "created_at"),
        # Índice composto para rate limiting: empresa + data de criação
        sa.Index("ix_ai_analyses_company_created", "company_id", "created_at"),
    )
