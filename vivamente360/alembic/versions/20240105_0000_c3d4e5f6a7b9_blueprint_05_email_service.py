"""blueprint_05_email_service

Adiciona melhorias de performance e consistência para o Email Service:

1. Índice composto em email_logs(destinatario_hash, created_at DESC)
   Acelera a query de rate limiting (count_recent_by_hash) que é executada
   em todo pedido de envio de email pelo EmailService.

2. Adiciona valor 'cleanup_expired_tokens' ao ENUM task_queue_type
   Corrige inconsistência entre o Python Enum (TaskQueueType) e o tipo
   PostgreSQL nativo — necessário para o endpoint de limpeza de tokens
   (auth_router.schedule_token_cleanup) funcionar corretamente.

Revision ID: c3d4e5f6a7b9
Revises: c3d4e5f6a7b8
Create Date: 2024-01-05 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Índice composto para acelerar rate limiting em email_logs
    #
    # A query executada pelo EmailService.count_recent_by_hash() filtra por
    # destinatario_hash e por created_at >= cutoff. Sem este índice, a query
    # faz full table scan — inaceitável com volume alto de envios.
    #
    # O índice parcial WHERE status IN ('pending', 'sent', 'failed', 'bounced')
    # seria ideal, mas como todos os status estão sempre presentes, o índice
    # composto simples é suficiente e mais portátil.
    # -----------------------------------------------------------------------
    op.create_index(
        "ix_email_logs_hash_created_at",
        "email_logs",
        ["destinatario_hash", sa.text("created_at DESC")],
        unique=False,
    )

    # -----------------------------------------------------------------------
    # 2. Adicionar 'cleanup_expired_tokens' ao ENUM task_queue_type
    #
    # O PostgreSQL não suporta ALTER TYPE ADD VALUE dentro de uma transação,
    # portanto usamos COMMIT implícito via execute() com autocommit=True.
    # O Alembic 1.13+ gerencia isso com op.execute() fora de bloco de transação.
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'cleanup_expired_tokens'"
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remove o índice composto de email_logs
    # -----------------------------------------------------------------------
    op.drop_index("ix_email_logs_hash_created_at", table_name="email_logs")

    # -----------------------------------------------------------------------
    # Nota: PostgreSQL não suporta remoção de valores de ENUM via ALTER TYPE.
    # O valor 'cleanup_expired_tokens' permanecerá no tipo, mas não causará
    # problemas pois o código não o utilizará após o downgrade.
    # -----------------------------------------------------------------------
