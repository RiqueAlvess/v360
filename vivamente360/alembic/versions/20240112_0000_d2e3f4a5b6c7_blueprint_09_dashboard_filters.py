"""blueprint_09_dashboard_filters

Módulo 09 — Dashboard Avançado: Filtros & Comparativo

Alterações:
    1. Adiciona colunas de filtro direto em fact_score_dimensao:
        - unidade_id UUID FK organizational_units(id) SET NULL, nullable
        - setor_id   UUID FK sectors(id)              SET NULL, nullable
        - cargo_id   UUID FK job_positions(id)         SET NULL, nullable
       Permite filtragem eficiente sem JOIN em dim_estrutura (Regra R3).

    2. Cria índices compostos para filtros:
        - idx_fact_unidade (campaign_id, unidade_id)
        - idx_fact_setor   (campaign_id, setor_id)

    3. Adiciona valor 'refresh_campaign_comparison' ao ENUM task_queue_type
       para o worker que atualiza a view materializada após rebuild de analytics.

    4. Cria view materializada campaign_comparison:
        SELECT campaign_id, dimensao, AVG(score_medio), COUNT(DISTINCT setor_id)
        FROM fact_score_dimensao GROUP BY campaign_id, dimensao
       Usada pelo endpoint GET /dashboard/compare — leitura O(1) por dimensão.

    5. Cria índice único em campaign_comparison (campaign_id, dimensao)
       habilitando REFRESH MATERIALIZED VIEW CONCURRENTLY nos workers.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2024-01-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Adiciona colunas de filtro direto em fact_score_dimensao
    #    (desnormalização intencional: evita JOIN em dim_estrutura no hot path)
    # -----------------------------------------------------------------------
    op.add_column(
        "fact_score_dimensao",
        sa.Column(
            "unidade_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "fact_score_dimensao",
        sa.Column(
            "setor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sectors.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "fact_score_dimensao",
        sa.Column(
            "cargo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("job_positions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # -----------------------------------------------------------------------
    # 2. Índices compostos para filtros de alta frequência
    # -----------------------------------------------------------------------
    op.create_index(
        "idx_fact_unidade",
        "fact_score_dimensao",
        ["campaign_id", "unidade_id"],
    )
    op.create_index(
        "idx_fact_setor",
        "fact_score_dimensao",
        ["campaign_id", "setor_id"],
    )

    # -----------------------------------------------------------------------
    # 3. Adiciona task type para refresh da view materializada
    #    (ADD VALUE IF NOT EXISTS — idempotente mesmo em re-execuções)
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'refresh_campaign_comparison'"
    )

    # -----------------------------------------------------------------------
    # 4. Cria view materializada campaign_comparison
    #    Atualizada por worker assíncrono após cada rebuild_analytics (Regra R3).
    #    Elimina cálculo em runtime no endpoint GET /dashboard/compare.
    # -----------------------------------------------------------------------
    op.execute(
        """
        CREATE MATERIALIZED VIEW campaign_comparison AS
        SELECT
            campaign_id,
            dimensao,
            AVG(score_medio)         AS score_campanha,
            COUNT(DISTINCT setor_id) AS total_setores
        FROM fact_score_dimensao
        GROUP BY campaign_id, dimensao
        WITH NO DATA
        """
    )

    # -----------------------------------------------------------------------
    # 5. Índice único — habilita REFRESH MATERIALIZED VIEW CONCURRENTLY
    #    e cobre a consulta do comparativo por campaign_id + dimensao
    # -----------------------------------------------------------------------
    op.execute(
        "CREATE UNIQUE INDEX idx_campaign_comparison_pk "
        "ON campaign_comparison (campaign_id, dimensao)"
    )


def downgrade() -> None:
    # Remove view materializada (seus índices são removidos automaticamente)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS campaign_comparison")

    # Remove índices de filtro em fact_score_dimensao
    op.drop_index("idx_fact_setor", table_name="fact_score_dimensao")
    op.drop_index("idx_fact_unidade", table_name="fact_score_dimensao")

    # Remove colunas de filtro
    op.drop_column("fact_score_dimensao", "cargo_id")
    op.drop_column("fact_score_dimensao", "setor_id")
    op.drop_column("fact_score_dimensao", "unidade_id")

    # Nota: valores de ENUM não podem ser removidos no PostgreSQL sem recriar o tipo.
    # 'refresh_campaign_comparison' permanece no ENUM task_queue_type após downgrade.
