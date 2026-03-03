"""blueprint_03_action_plans

Implementa o módulo de Plano de Ação (CRUD completo):

Tabelas criadas:
    - action_plans  — planos de ação vinculados a campanhas e dimensões de risco

ENUMs criados (PostgreSQL nativos):
    - action_plan_status  — pendente | em_andamento | concluido | cancelado

Políticas de RLS:
    - rls_action_plans ON action_plans — isolamento multi-tenant por company_id

Regra R5: RLS ativa em action_plans — o banco é a última linha de defesa.
Regra R1: Constraints CHECK em status e nivel_risco garantem integridade dos dados.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2024-01-07 00:00:00.000000

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
    # 1. ENUM action_plan_status
    #
    # Criado explicitamente para controle via Alembic (downgrade seguro).
    # -----------------------------------------------------------------------
    action_plan_status = postgresql.ENUM(
        "pendente",
        "em_andamento",
        "concluido",
        "cancelado",
        name="action_plan_status",
    )
    action_plan_status.create(op.get_bind())

    # -----------------------------------------------------------------------
    # 2. action_plans — planos de ação vinculados a campanhas
    #
    # Soft delete via status='cancelado' — sem hard delete.
    # nivel_risco reutiliza o ENUM existente 'nivel_risco' do star schema.
    # -----------------------------------------------------------------------
    op.create_table(
        "action_plans",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("titulo", sa.Text, nullable=False),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("dimensao", sa.String(50), nullable=True),
        sa.Column(
            "unidade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "setor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "responsavel_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("responsavel_externo", sa.String(200), nullable=True),
        sa.Column(
            "nivel_risco",
            sa.Enum(
                "aceitavel",
                "moderado",
                "importante",
                "critico",
                name="nivel_risco",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pendente",
                "em_andamento",
                "concluido",
                "cancelado",
                name="action_plan_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pendente",
        ),
        sa.Column("prazo", sa.Date, nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Índices para as consultas mais frequentes
    op.create_index(
        "ix_action_plans_campaign_id",
        "action_plans",
        ["campaign_id"],
    )
    op.create_index(
        "ix_action_plans_company_id",
        "action_plans",
        ["company_id"],
    )
    # Índice composto para filtrar por campanha + status (consulta principal do dashboard)
    op.create_index(
        "ix_action_plans_campaign_status",
        "action_plans",
        ["campaign_id", "status"],
    )
    # Índice composto para filtrar por campanha + nivel_risco
    op.create_index(
        "ix_action_plans_campaign_nivel_risco",
        "action_plans",
        ["campaign_id", "nivel_risco"],
    )

    # -----------------------------------------------------------------------
    # 3. RLS em action_plans — isolamento multi-tenant por company_id
    #
    # Regra R5: RLS é a última linha de defesa. O código NÃO deve depender
    # de filtros manuais por company_id para garantir o isolamento.
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE action_plans ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rls_action_plans ON action_plans
        USING (company_id = current_setting('app.company_id')::uuid)
        """
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remover na ordem inversa, respeitando dependências FK
    # -----------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS rls_action_plans ON action_plans")

    op.drop_index("ix_action_plans_campaign_nivel_risco", table_name="action_plans")
    op.drop_index("ix_action_plans_campaign_status", table_name="action_plans")
    op.drop_index("ix_action_plans_company_id", table_name="action_plans")
    op.drop_index("ix_action_plans_campaign_id", table_name="action_plans")
    op.drop_table("action_plans")

    # Remover ENUM criado explicitamente nesta migration
    action_plan_status = postgresql.ENUM(name="action_plan_status")
    action_plan_status.drop(op.get_bind())
