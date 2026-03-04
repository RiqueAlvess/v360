"""blueprint_07_whistleblower

Módulo 07 — Canal de Denúncias Anônimo (NR-1 Compliance — Portaria MTE 1.419/2024)

Alterações:
    1. Adiciona coluna 'slug' à tabela companies (VARCHAR 100, nullable, unique).
       Índice único: ix_companies_slug.
       Permite URLs públicas do tipo /denuncia/{slug}/submit.

    2. Cria tabela whistleblower_reports:
        - id UUID PK (gen_random_uuid())
        - company_id UUID FK companies(id) CASCADE — contexto de tenant
        - token_hash VARCHAR(64) NOT NULL UNIQUE — SHA-256 do token dado ao denunciante
          O token raw é exibido apenas uma vez ao denunciante e NUNCA persiste no banco.
        - categoria VARCHAR(50) NOT NULL — categoria da denúncia (ver CHECK constraint)
        - descricao TEXT NOT NULL — conteúdo do relato
        - anonimo BOOLEAN NOT NULL DEFAULT TRUE
        - nome_opcional TEXT nullable — apenas se anonimo=FALSE (decisão do denunciante)
        - status VARCHAR(20) NOT NULL DEFAULT 'recebido' — ciclo de vida do relato
        - resposta_institucional TEXT nullable — preenchido pelo admin/compliance
        - respondido_por UUID FK users(id) SET NULL nullable
        - respondido_em TIMESTAMPTZ nullable
        - created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

    3. Ativa Row Level Security em whistleblower_reports.
       Política: company_id = current_setting('app.company_id', true)::uuid

    4. Cria índices compostos para performance:
        - ix_whistleblower_reports_company_id
        - ix_whistleblower_reports_token_hash (unique)
        - ix_whistleblower_reports_status
        - ix_whistleblower_reports_created_at
        - ix_whistleblower_reports_company_status (company_id, status)

    5. Adiciona valor 'notify_whistleblower_admin' ao ENUM task_queue_type
       para notificação assíncrona de admins ao receber novo relato.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2024-01-10 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Adicionar coluna slug à tabela companies
    # -----------------------------------------------------------------------
    op.add_column(
        "companies",
        sa.Column("slug", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_companies_slug",
        "companies",
        ["slug"],
        unique=True,
    )

    # -----------------------------------------------------------------------
    # 2. Criar tabela whistleblower_reports
    # -----------------------------------------------------------------------
    op.create_table(
        "whistleblower_reports",
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
        # SHA-256 do token entregue ao denunciante — token raw NUNCA persiste
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("categoria", sa.String(50), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column(
            "anonimo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        # Preenchido APENAS quando o denunciante optar por se identificar (anonimo=FALSE)
        sa.Column("nome_opcional", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'recebido'"),
        ),
        sa.Column("resposta_institucional", sa.Text(), nullable=True),
        sa.Column(
            "respondido_por",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "respondido_em",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("token_hash", name="uq_whistleblower_reports_token_hash"),
        sa.CheckConstraint(
            "categoria IN ("
            "'assedio_moral', 'assedio_sexual', 'discriminacao', "
            "'violencia', 'corrupcao', 'outro')",
            name="ck_whistleblower_reports_categoria",
        ),
        sa.CheckConstraint(
            "status IN ('recebido', 'em_analise', 'concluido', 'arquivado')",
            name="ck_whistleblower_reports_status",
        ),
    )

    # Índices para performance de listagem e lookup por token
    op.create_index(
        "ix_whistleblower_reports_company_id",
        "whistleblower_reports",
        ["company_id"],
    )
    op.create_index(
        "ix_whistleblower_reports_token_hash",
        "whistleblower_reports",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_whistleblower_reports_status",
        "whistleblower_reports",
        ["status"],
    )
    op.create_index(
        "ix_whistleblower_reports_created_at",
        "whistleblower_reports",
        ["created_at"],
    )
    op.create_index(
        "ix_whistleblower_reports_company_status",
        "whistleblower_reports",
        ["company_id", "status"],
    )

    # -----------------------------------------------------------------------
    # 3. Ativar Row Level Security e criar política de isolamento por empresa
    #    Política permissiva: somente relatos da empresa autenticada são visíveis.
    #    current_setting(..., true) retorna NULL se não configurado (sem erro).
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE whistleblower_reports ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rls_whistleblower_reports ON whistleblower_reports
            AS PERMISSIVE
            FOR ALL
            USING (company_id = current_setting('app.company_id', true)::uuid)
        """
    )

    # -----------------------------------------------------------------------
    # 4. Adicionar valor ao ENUM task_queue_type para notificação de admins
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'notify_whistleblower_admin'"
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # 3. Remover política RLS e desativar RLS
    # -----------------------------------------------------------------------
    op.execute(
        "DROP POLICY IF EXISTS rls_whistleblower_reports ON whistleblower_reports"
    )
    op.execute("ALTER TABLE whistleblower_reports DISABLE ROW LEVEL SECURITY")

    # -----------------------------------------------------------------------
    # 2. Remover índices e tabela whistleblower_reports
    # -----------------------------------------------------------------------
    op.drop_index(
        "ix_whistleblower_reports_company_status",
        table_name="whistleblower_reports",
    )
    op.drop_index(
        "ix_whistleblower_reports_created_at",
        table_name="whistleblower_reports",
    )
    op.drop_index(
        "ix_whistleblower_reports_status",
        table_name="whistleblower_reports",
    )
    op.drop_index(
        "ix_whistleblower_reports_token_hash",
        table_name="whistleblower_reports",
    )
    op.drop_index(
        "ix_whistleblower_reports_company_id",
        table_name="whistleblower_reports",
    )
    op.drop_table("whistleblower_reports")

    # -----------------------------------------------------------------------
    # 1. Remover slug da tabela companies
    # -----------------------------------------------------------------------
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_column("companies", "slug")

    # Nota: remover valores de ENUM não é suportado diretamente no PostgreSQL.
    # O valor 'notify_whistleblower_admin' permanece no tipo — é seguro (não processado).
