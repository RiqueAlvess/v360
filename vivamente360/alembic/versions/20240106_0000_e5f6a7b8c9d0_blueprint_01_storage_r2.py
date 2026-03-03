"""blueprint_01_storage_r2

Implementa a camada de armazenamento de arquivos com Cloudflare R2 (Módulo 01).

Tabela criada:
    file_assets — metadados de arquivos armazenados no Cloudflare R2.
        O binário do arquivo nunca fica no servidor FastAPI; apenas os
        metadados (r2_key, filename, mime_type, size_bytes, contexto,
        referencia_id) são persistidos aqui.

RLS:
    Política tenant_file_assets garante que empresa A não acessa arquivos
    da empresa B. O filtro é feito pelo banco via current_setting('app.company_id').

Índices criados:
    - ix_file_assets_company_id    ON file_assets(company_id)
    - ix_file_assets_referencia_id ON file_assets(referencia_id)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2024-01-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Tabela file_assets
    #
    # Armazena apenas metadados. O binário fica no Cloudflare R2 identificado
    # pela coluna r2_key (único no bucket: company/{id}/{contexto}/{uuid}.ext).
    # -----------------------------------------------------------------------
    op.create_table(
        "file_assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("r2_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("contexto", sa.String(50), nullable=False),
        sa.Column(
            "referencia_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("deletado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("r2_key", name="uq_file_assets_r2_key"),
    )

    # -----------------------------------------------------------------------
    # 2. Índices para queries frequentes
    # -----------------------------------------------------------------------
    op.create_index("ix_file_assets_company_id", "file_assets", ["company_id"])
    op.create_index(
        "ix_file_assets_referencia_id",
        "file_assets",
        ["referencia_id"],
        postgresql_where=sa.text("referencia_id IS NOT NULL"),
    )

    # -----------------------------------------------------------------------
    # 3. Row Level Security — Multi-tenancy
    #
    # A política garante que cada empresa veja apenas seus próprios arquivos.
    # O SET LOCAL app.company_id é executado pela dependência get_current_user()
    # no início de cada request autenticado.
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE file_assets ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_file_assets ON file_assets
            USING (company_id = current_setting('app.company_id')::uuid)
        """
    )

    # -----------------------------------------------------------------------
    # 4. Bypass RLS para superuser (necessário para migrations e workers)
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TABLE file_assets FORCE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remove política RLS, índices e tabela na ordem inversa
    # -----------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS tenant_file_assets ON file_assets")
    op.execute("ALTER TABLE file_assets DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_file_assets_referencia_id", table_name="file_assets")
    op.drop_index("ix_file_assets_company_id", table_name="file_assets")

    op.drop_table("file_assets")
