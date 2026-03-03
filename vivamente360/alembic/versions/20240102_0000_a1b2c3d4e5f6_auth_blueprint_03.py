"""auth_blueprint_03

Adiciona campo nome (nullable) na tabela users e o valor 'cleanup_expired_tokens'
no tipo ENUM task_queue_type — ambas as alterações necessárias para o Blueprint 03
(autenticação JWT + rotação de tokens + limpeza assíncrona de tokens expirados).

Revision ID: a1b2c3d4e5f6
Revises: 5e6f7a8b9c0d
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5e6f7a8b9c0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Adicionar coluna nome à tabela users (nullable — retrocompatível)
    # -----------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("nome", sa.String(255), nullable=True),
    )

    # -----------------------------------------------------------------------
    # 2. Adicionar valor 'cleanup_expired_tokens' ao ENUM task_queue_type
    #
    # PostgreSQL 12+ permite ADD VALUE dentro de transações.
    # IF NOT EXISTS previne erro em re-execuções acidentais.
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'cleanup_expired_tokens'"
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Remover coluna nome da tabela users
    # -----------------------------------------------------------------------
    op.drop_column("users", "nome")

    # -----------------------------------------------------------------------
    # 2. Remover valor do ENUM task_queue_type
    #
    # PostgreSQL não suporta DROP VALUE de ENUMs nativamente.
    # A estratégia segura é recriar o tipo sem o valor removido.
    # -----------------------------------------------------------------------
    op.execute(
        """
        -- Garante que nenhuma linha use o valor antes de recriar o tipo
        DELETE FROM task_queue WHERE tipo = 'cleanup_expired_tokens';

        -- Recria o ENUM sem o valor cleanup_expired_tokens
        ALTER TYPE task_queue_type RENAME TO task_queue_type_old;

        CREATE TYPE task_queue_type AS ENUM (
            'compute_scores',
            'send_email',
            'send_invitations',
            'generate_report'
        );

        ALTER TABLE task_queue
            ALTER COLUMN tipo TYPE task_queue_type
            USING tipo::text::task_queue_type;

        DROP TYPE task_queue_type_old;
        """
    )
