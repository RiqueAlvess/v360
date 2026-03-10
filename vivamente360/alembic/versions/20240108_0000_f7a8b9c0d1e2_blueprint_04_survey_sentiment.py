"""blueprint_04_survey_sentiment

Módulo 04 — Survey HSE-IT: Campo Livre & Sentimento

Alterações:
    1. survey_responses — adiciona três colunas para campo livre e análise de sentimento:
        - texto_livre TEXT (nullable) — texto criptografado AES-256-GCM em repouso
        - sentimento VARCHAR(20) (nullable) — classificação qualitativa (enum)
        - sentimento_score NUMERIC(4,3) (nullable) — score numérico -1.0 a +1.0

    2. Cria o tipo ENUM nativo 'sentimento_type' no PostgreSQL:
        valores: positivo | neutro | negativo | critico

    3. fact_score_dimensao — adiciona coluna para sentimento médio agregado:
        - sentimento_score_medio NUMERIC(4,3) (nullable)
          Populado pelo RebuildAnalyticsHandler com a média dos sentimento_score
          das respostas da campanha.

    4. task_queue — adiciona valor 'analyze_sentiment' ao ENUM task_queue_type.
       Necessário para que a task possa ser enfileirada e processada pelo worker.

Notas LGPD:
    - texto_livre nunca persiste em plaintext — sempre criptografado via CryptoService.
    - sentimento e sentimento_score são metadados derivados; não são dados pessoais.
    - Descriptografia ocorre apenas no AnalyzeSentimentHandler, em memória, durante
      a chamada à IA.

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2024-01-08 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum de classificação de sentimento (novo tipo nativo PostgreSQL)
# Usa postgresql.ENUM para evitar _on_table_create do sa.Enum (DuplicateObjectError)
SENTIMENTO_TYPE_ENUM = postgresql.ENUM(
    "positivo",
    "neutro",
    "negativo",
    "critico",
    name="sentimento_type",
    create_type=False,
)


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Criar tipo ENUM nativo para sentimento_type (idempotente via DO $$)
    # -----------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sentimento_type') THEN
                CREATE TYPE sentimento_type AS ENUM ('positivo', 'neutro', 'negativo', 'critico');
            END IF;
        END$$;
    """)

    # -----------------------------------------------------------------------
    # 2. Adicionar colunas à tabela survey_responses
    # -----------------------------------------------------------------------
    op.add_column(
        "survey_responses",
        sa.Column("texto_livre", sa.Text, nullable=True),
    )
    op.add_column(
        "survey_responses",
        sa.Column(
            "sentimento",
            postgresql.ENUM(
                "positivo",
                "neutro",
                "negativo",
                "critico",
                name="sentimento_type",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "survey_responses",
        sa.Column("sentimento_score", sa.Numeric(4, 3), nullable=True),
    )

    # -----------------------------------------------------------------------
    # 3. Adicionar coluna sentimento_score_medio à tabela fact_score_dimensao
    # -----------------------------------------------------------------------
    op.add_column(
        "fact_score_dimensao",
        sa.Column("sentimento_score_medio", sa.Numeric(4, 3), nullable=True),
    )

    # -----------------------------------------------------------------------
    # 4. Adicionar valor 'analyze_sentiment' ao ENUM task_queue_type
    #    (compatível com PostgreSQL — ALTER TYPE ... ADD VALUE)
    # -----------------------------------------------------------------------
    op.execute("ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'analyze_sentiment'")


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remover em ordem inversa
    # -----------------------------------------------------------------------

    # 4. Remover valor do ENUM task_queue_type não é suportado diretamente
    #    no PostgreSQL — recriar o tipo sem o valor removido seria destrutivo.
    #    Deixamos o valor no ENUM (é seguro — apenas não será enfileirado).

    # 3. Remover coluna sentimento_score_medio de fact_score_dimensao
    op.drop_column("fact_score_dimensao", "sentimento_score_medio")

    # 2. Remover colunas de survey_responses
    op.drop_column("survey_responses", "sentimento_score")
    op.drop_column("survey_responses", "sentimento")
    op.drop_column("survey_responses", "texto_livre")

    # 1. Remover tipo ENUM sentimento_type
    SENTIMENTO_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
