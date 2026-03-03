"""blueprint_02_checklist_nr1

Implementa o módulo completo de Checklist NR-1:

Tabelas criadas:
    - checklist_templates   — templates canônicos dos itens NR-1 (seed obrigatório)
    - file_assets           — ativos de arquivo compartilhados (evidências, relatórios)
    - checklist_items       — itens de conformidade por campanha, com toggle e evidências

Políticas de RLS:
    - rls_checklist_items ON checklist_items — isolamento multi-tenant por company_id

Regra R5: RLS ativa em checklist_items — o banco é a última linha de defesa.
Regra R2: Tabela file_assets é compartilhada entre módulos (evidências, relatórios).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2024-01-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. checklist_templates — templates canônicos dos itens NR-1
    #
    # Tabela de referência imutável em runtime — populada via seed.
    # Não tem timestamps pois é gerenciada por migrações/seeds, não pelo app.
    # -----------------------------------------------------------------------
    op.create_table(
        "checklist_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("categoria", sa.String(100), nullable=False),
        sa.Column(
            "obrigatorio",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("prazo_dias", sa.Integer, nullable=True),
        sa.Column(
            "ordem",
            sa.SmallInteger,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_checklist_templates_categoria",
        "checklist_templates",
        ["categoria"],
    )
    op.create_index(
        "ix_checklist_templates_codigo",
        "checklist_templates",
        ["codigo"],
        unique=True,
    )

    # -----------------------------------------------------------------------
    # 2. file_assets — ativos de arquivo compartilhados entre módulos
    #
    # Armazena metadados de arquivos físicos hospedados no Cloudflare R2.
    # Arquivos físicos NUNCA são servidos diretamente — apenas via signed URLs.
    # Soft delete: o campo `deletado` indica exclusão lógica; storage_key
    # permanece para eventual limpeza assíncrona pelo worker.
    # -----------------------------------------------------------------------
    op.create_table(
        "file_assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contexto", sa.String(100), nullable=False),
        sa.Column("referencia_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("nome_original", sa.String(500), nullable=False),
        sa.Column("tamanho_bytes", sa.BigInteger, nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column(
            "deletado",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deletado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_file_assets_company_id", "file_assets", ["company_id"])
    op.create_index("ix_file_assets_referencia_id", "file_assets", ["referencia_id"])
    # Índice composto para busca de evidências por contexto e referência
    op.create_index(
        "ix_file_assets_contexto_referencia",
        "file_assets",
        ["contexto", "referencia_id"],
    )

    # -----------------------------------------------------------------------
    # 3. checklist_items — itens de conformidade por campanha
    #
    # Cada campanha recebe um conjunto de checklist_items criado automaticamente
    # a partir dos checklist_templates (hook no CampaignService).
    # -----------------------------------------------------------------------
    op.create_table(
        "checklist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("checklist_templates.id"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "concluido",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "concluido_por",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("observacao", sa.Text, nullable=True),
        sa.Column("prazo", sa.Date, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Garante que cada template só aparece uma vez por campanha
        sa.UniqueConstraint(
            "campaign_id",
            "template_id",
            name="uq_checklist_items_campaign_template",
        ),
    )
    op.create_index(
        "ix_checklist_items_campaign_id",
        "checklist_items",
        ["campaign_id"],
    )
    op.create_index(
        "ix_checklist_items_company_id",
        "checklist_items",
        ["company_id"],
    )
    # Índice composto para filtrar itens pendentes/concluídos de uma campanha
    op.create_index(
        "ix_checklist_items_campaign_concluido",
        "checklist_items",
        ["campaign_id", "concluido"],
    )

    # -----------------------------------------------------------------------
    # 4. RLS em checklist_items — isolamento multi-tenant por company_id
    #
    # Regra R5: RLS é a última linha de defesa. O código NÃO deve depender
    # de filtros manuais por company_id para garantir o isolamento.
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE checklist_items ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rls_checklist_items ON checklist_items
        USING (company_id = current_setting('app.company_id')::uuid)
        """
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remover na ordem inversa, respeitando dependências FK
    # -----------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS rls_checklist_items ON checklist_items")

    op.drop_index("ix_checklist_items_campaign_concluido", table_name="checklist_items")
    op.drop_index("ix_checklist_items_company_id", table_name="checklist_items")
    op.drop_index("ix_checklist_items_campaign_id", table_name="checklist_items")
    op.drop_table("checklist_items")

    op.drop_index("ix_file_assets_contexto_referencia", table_name="file_assets")
    op.drop_index("ix_file_assets_referencia_id", table_name="file_assets")
    op.drop_index("ix_file_assets_company_id", table_name="file_assets")
    op.drop_table("file_assets")

    op.drop_index("ix_checklist_templates_codigo", table_name="checklist_templates")
    op.drop_index("ix_checklist_templates_categoria", table_name="checklist_templates")
    op.drop_table("checklist_templates")
