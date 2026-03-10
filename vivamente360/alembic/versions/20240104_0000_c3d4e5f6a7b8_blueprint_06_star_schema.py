"""blueprint_06_star_schema

Implementa o Modelo Estrela (Star Schema) de analytics para o dashboard.

Tabelas criadas:
    Estrutura organizacional (suporte ao dim_estrutura):
    - organizational_units  — unidades organizacionais da empresa
    - sectors               — setores dentro de uma unidade
    - job_positions         — cargos/funções dos respondentes

    Dimensões do modelo estrela:
    - dim_tempo             — dimensão de tempo (data, ano, mês, trimestre, etc.)
    - dim_estrutura         — dimensão estrutural (snapshot de empresa/unidade/setor/cargo)

    Tabela fato:
    - fact_score_dimensao   — scores pré-computados por dimensão HSE-IT

Índices criados:
    - idx_fact_campaign_dimensao    ON fact_score_dimensao (campaign_id, dimensao)
    - idx_fact_estrutura_risco      ON fact_score_dimensao (dim_estrutura_id, nivel_risco)

Regra R3: O dashboard NUNCA calcula em tempo real.
Os dados de fact_score_dimensao são populados por workers assíncronos.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2024-01-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ENUM para as 7 dimensões HSE-IT adaptado para o contexto brasileiro
# Usa postgresql.ENUM para evitar _on_table_create do sa.Enum (DuplicateObjectError)
DIMENSAO_HSE_ENUM = postgresql.ENUM(
    "demandas",
    "controle",
    "suporte_gestao",
    "relacionamentos",
    "papel_funcao",
    "mudancas",
    "suporte_colegas",
    name="dimensao_hse",
    create_type=False,
)

# ENUM para níveis de risco — ordem crescente de severidade
NIVEL_RISCO_ENUM = postgresql.ENUM(
    "aceitavel",
    "moderado",
    "importante",
    "critico",
    name="nivel_risco",
    create_type=False,
)


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Criar tipos ENUM nativos do PostgreSQL (idempotente via DO $$)
    # -----------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dimensao_hse') THEN
                CREATE TYPE dimensao_hse AS ENUM ('demandas', 'controle', 'suporte_gestao', 'relacionamentos', 'papel_funcao', 'mudancas', 'suporte_colegas');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'nivel_risco') THEN
                CREATE TYPE nivel_risco AS ENUM ('aceitavel', 'moderado', 'importante', 'critico');
            END IF;
        END$$;
    """)

    # -----------------------------------------------------------------------
    # 2. organizational_units — unidades organizacionais (ex: Filial SP, HQ)
    # -----------------------------------------------------------------------
    op.create_table(
        "organizational_units",
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
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
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
    op.create_index(
        "ix_organizational_units_company_id",
        "organizational_units",
        ["company_id"],
    )

    # -----------------------------------------------------------------------
    # 3. sectors — setores dentro de uma unidade (ex: RH, TI, Financeiro)
    # -----------------------------------------------------------------------
    op.create_table(
        "sectors",
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
        sa.Column(
            "unidade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_sectors_company_id", "sectors", ["company_id"])

    # -----------------------------------------------------------------------
    # 4. job_positions — cargos/funções dos respondentes
    # -----------------------------------------------------------------------
    op.create_table(
        "job_positions",
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
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("ativo", sa.Boolean, nullable=False, server_default=sa.text("true")),
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
    op.create_index("ix_job_positions_company_id", "job_positions", ["company_id"])

    # -----------------------------------------------------------------------
    # 5. dim_tempo — dimensão de tempo para o modelo estrela
    #    Decompõe a data em componentes para filtros analíticos eficientes
    # -----------------------------------------------------------------------
    op.create_table(
        "dim_tempo",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("data", sa.Date, nullable=False),
        sa.Column("ano", sa.SmallInteger, nullable=False),
        sa.Column("mes", sa.SmallInteger, nullable=False),
        sa.Column("dia", sa.SmallInteger, nullable=False),
        sa.Column("trimestre", sa.SmallInteger, nullable=False),
        sa.Column("dia_semana", sa.SmallInteger, nullable=False),
        sa.Column("semana_ano", sa.SmallInteger, nullable=False),
        sa.UniqueConstraint("data", name="uq_dim_tempo_data"),
    )
    op.create_index("ix_dim_tempo_data", "dim_tempo", ["data"])

    # -----------------------------------------------------------------------
    # 6. dim_estrutura — snapshot da hierarquia organizacional no momento da análise
    #    Preserva histórico mesmo após mudanças na estrutura
    # -----------------------------------------------------------------------
    op.create_table(
        "dim_estrutura",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # FKs opcionais — campanhas podem não ter estrutura organizacional definida
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
            "cargo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Snapshots de nomes para preservar histórico após renomeações
        sa.Column("unidade_nome", sa.String(200), nullable=True),
        sa.Column("setor_nome", sa.String(200), nullable=True),
        sa.Column("cargo_nome", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_dim_estrutura_company_id", "dim_estrutura", ["company_id"])

    # -----------------------------------------------------------------------
    # 7. fact_score_dimensao — coração do modelo estrela
    #    Scores pré-computados por dimensão HSE-IT, por estrutura e tempo
    #    Constraint UNIQUE garante idempotência no upsert do worker
    # -----------------------------------------------------------------------
    op.create_table(
        "fact_score_dimensao",
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
            "dim_tempo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dim_tempo.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "dim_estrutura_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dim_estrutura.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "dimensao",
            postgresql.ENUM(
                "demandas",
                "controle",
                "suporte_gestao",
                "relacionamentos",
                "papel_funcao",
                "mudancas",
                "suporte_colegas",
                name="dimensao_hse",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("score_medio", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "nivel_risco",
            postgresql.ENUM(
                "aceitavel",
                "moderado",
                "importante",
                "critico",
                name="nivel_risco",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("total_respostas", sa.Integer, nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Constraint UNIQUE para idempotência do INSERT ... ON CONFLICT DO UPDATE
        sa.UniqueConstraint(
            "campaign_id",
            "dim_tempo_id",
            "dim_estrutura_id",
            "dimensao",
            name="uq_fact_score_dimensao",
        ),
    )

    # Índices de performance para queries do dashboard
    op.create_index(
        "idx_fact_campaign_dimensao",
        "fact_score_dimensao",
        ["campaign_id", "dimensao"],
    )
    op.create_index(
        "idx_fact_estrutura_risco",
        "fact_score_dimensao",
        ["dim_estrutura_id", "nivel_risco"],
    )
    op.create_index(
        "ix_fact_score_campaign_id",
        "fact_score_dimensao",
        ["campaign_id"],
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remover em ordem inversa respeitando dependências de FK
    # -----------------------------------------------------------------------
    op.drop_index("ix_fact_score_campaign_id", table_name="fact_score_dimensao")
    op.drop_index("idx_fact_estrutura_risco", table_name="fact_score_dimensao")
    op.drop_index("idx_fact_campaign_dimensao", table_name="fact_score_dimensao")
    op.drop_table("fact_score_dimensao")

    op.drop_index("ix_dim_estrutura_company_id", table_name="dim_estrutura")
    op.drop_table("dim_estrutura")

    op.drop_index("ix_dim_tempo_data", table_name="dim_tempo")
    op.drop_table("dim_tempo")

    op.drop_index("ix_job_positions_company_id", table_name="job_positions")
    op.drop_table("job_positions")

    op.drop_index("ix_sectors_company_id", table_name="sectors")
    op.drop_table("sectors")

    op.drop_index("ix_organizational_units_company_id", table_name="organizational_units")
    op.drop_table("organizational_units")

    NIVEL_RISCO_ENUM.drop(op.get_bind(), checkfirst=True)
    DIMENSAO_HSE_ENUM.drop(op.get_bind(), checkfirst=True)
