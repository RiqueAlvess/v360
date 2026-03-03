"""blueprint_04_task_queue

Adiciona campos de controle de ciclo de vida à tabela task_queue e cria o
índice parcial de alta performance para o worker (WHERE status = 'pending').

Campos adicionados:
    - max_tentativas  INTEGER NOT NULL DEFAULT 3
    - iniciado_em     TIMESTAMPTZ nullable  (quando o worker começou a processar)
    - concluido_em    TIMESTAMPTZ nullable  (quando a tarefa foi concluída ou falhou)
    - erro            TEXT nullable         (último traceback/mensagem de erro)

Índice criado:
    - idx_task_queue_pending ON task_queue (agendado_para ASC) WHERE status = 'pending'
      Índice parcial — só indexa linhas relevantes para o worker, reduzindo
      I/O e acelerando o SELECT FOR UPDATE SKIP LOCKED.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2024-01-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Adicionar max_tentativas — controla o limite de retries por tarefa
    # -----------------------------------------------------------------------
    op.add_column(
        "task_queue",
        sa.Column(
            "max_tentativas",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )

    # -----------------------------------------------------------------------
    # 2. Adicionar iniciado_em — timestamp de quando o worker pegou a tarefa
    # -----------------------------------------------------------------------
    op.add_column(
        "task_queue",
        sa.Column(
            "iniciado_em",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # -----------------------------------------------------------------------
    # 3. Adicionar concluido_em — timestamp de conclusão (sucesso ou falha final)
    # -----------------------------------------------------------------------
    op.add_column(
        "task_queue",
        sa.Column(
            "concluido_em",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # -----------------------------------------------------------------------
    # 4. Adicionar erro — persiste o traceback/mensagem da última falha
    # -----------------------------------------------------------------------
    op.add_column(
        "task_queue",
        sa.Column(
            "erro",
            sa.Text(),
            nullable=True,
        ),
    )

    # -----------------------------------------------------------------------
    # 5. Índice parcial para performance do worker
    #
    # WHERE status = 'pending' limita o índice apenas às tarefas que o worker
    # precisa enxergar. Em sistemas com milhões de tarefas concluídas, este
    # índice permanece pequeno e eficiente — ao contrário de um índice composto
    # convencional que indexaria todas as linhas.
    # -----------------------------------------------------------------------
    op.create_index(
        "idx_task_queue_pending",
        "task_queue",
        ["agendado_para"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Remover índice parcial antes de alterar colunas
    # -----------------------------------------------------------------------
    op.drop_index(
        "idx_task_queue_pending",
        table_name="task_queue",
        postgresql_where=sa.text("status = 'pending'"),
    )

    # -----------------------------------------------------------------------
    # Remover colunas na ordem inversa da criação
    # -----------------------------------------------------------------------
    op.drop_column("task_queue", "erro")
    op.drop_column("task_queue", "concluido_em")
    op.drop_column("task_queue", "iniciado_em")
    op.drop_column("task_queue", "max_tentativas")
