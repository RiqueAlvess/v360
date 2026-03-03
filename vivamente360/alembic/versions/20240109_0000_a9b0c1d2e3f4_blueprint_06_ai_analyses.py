"""blueprint_06_ai_analyses

Módulo 06 — Análise por IA via OpenRouter por Setor

Alterações:
    1. Cria a tabela ai_analyses com todos os campos definidos no blueprint:
        - id UUID PK
        - company_id UUID FK companies (RLS)
        - campaign_id UUID FK campaigns
        - setor_id UUID FK sectors (nullable — NULL = análise geral)
        - dimensao VARCHAR(50) nullable — NULL = todas as dimensões HSE-IT
        - tipo VARCHAR(30) NOT NULL — 'sentimento'|'diagnostico'|'recomendacoes'
        - status VARCHAR(20) NOT NULL DEFAULT 'pending'
        - model_usado VARCHAR(100) nullable
        - tokens_input INTEGER nullable
        - tokens_output INTEGER nullable
        - resultado JSONB nullable — output validado via Pydantic
        - erro TEXT nullable — mensagem de erro quando status='failed'
        - prompt_versao VARCHAR(20) nullable — rastreabilidade de prompts
        - created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        - updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

    2. Ativa Row Level Security na tabela ai_analyses com política por company_id.

    3. Cria índices compostos para performance:
        - (campaign_id, created_at) — listagem por campanha
        - (company_id, created_at) — rate limiting por empresa/hora

    4. Adiciona valor 'run_ai_analysis' ao ENUM task_queue_type.

Revision ID: a9b0c1d2e3f4
Revises: f7a8b9c0d1e2
Create Date: 2024-01-09 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Criar tabela ai_analyses
    # -----------------------------------------------------------------------
    op.create_table(
        "ai_analyses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "setor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dimensao", sa.String(50), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("model_usado", sa.String(100), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("resultado", JSONB, nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("prompt_versao", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('sentimento', 'diagnostico', 'recomendacoes')",
            name="ck_ai_analyses_tipo",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_ai_analyses_status",
        ),
    )

    # Índices para performance
    op.create_index(
        "ix_ai_analyses_company_id",
        "ai_analyses",
        ["company_id"],
    )
    op.create_index(
        "ix_ai_analyses_campaign_id",
        "ai_analyses",
        ["campaign_id"],
    )
    op.create_index(
        "ix_ai_analyses_setor_id",
        "ai_analyses",
        ["setor_id"],
    )
    op.create_index(
        "ix_ai_analyses_status",
        "ai_analyses",
        ["status"],
    )
    op.create_index(
        "ix_ai_analyses_campaign_created",
        "ai_analyses",
        ["campaign_id", "created_at"],
    )
    op.create_index(
        "ix_ai_analyses_company_created",
        "ai_analyses",
        ["company_id", "created_at"],
    )

    # -----------------------------------------------------------------------
    # 2. Ativar Row Level Security e criar política de isolamento por empresa
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE ai_analyses ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rls_ai_analyses ON ai_analyses
            USING (company_id = current_setting('app.company_id')::uuid)
        """
    )

    # -----------------------------------------------------------------------
    # 3. Adicionar valor 'run_ai_analysis' ao ENUM task_queue_type
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'run_ai_analysis'"
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # 3. Remover política RLS e desativar RLS (deve ser antes do drop table)
    # -----------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS rls_ai_analyses ON ai_analyses")
    op.execute("ALTER TABLE ai_analyses DISABLE ROW LEVEL SECURITY")

    # -----------------------------------------------------------------------
    # 2. Remover índices
    # -----------------------------------------------------------------------
    op.drop_index("ix_ai_analyses_company_created", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_campaign_created", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_status", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_setor_id", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_campaign_id", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_company_id", table_name="ai_analyses")

    # -----------------------------------------------------------------------
    # 1. Remover tabela ai_analyses
    # -----------------------------------------------------------------------
    op.drop_table("ai_analyses")

    # Nota: remover valores de ENUM não é suportado diretamente no PostgreSQL.
    # O valor 'run_ai_analysis' permanece no tipo (é seguro — não será enfileirado).
