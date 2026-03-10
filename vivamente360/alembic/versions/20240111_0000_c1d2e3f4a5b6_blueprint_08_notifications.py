"""blueprint_08_notifications

Módulo 08 — Notificações In-App

Alterações:
    1. Adiciona valor 'check_campaign_alerts' ao ENUM task_queue_type
       para o job diário de alertas de campanhas e planos de ação.

    2. Cria tabela notifications:
        - id UUID PK (gen_random_uuid())
        - company_id UUID FK companies(id) CASCADE — contexto multi-tenant
        - user_id UUID FK users(id) CASCADE — destinatário da notificação
        - tipo VARCHAR(50) NOT NULL — enum de tipos de eventos
        - titulo TEXT NOT NULL — título curto da notificação
        - mensagem TEXT NOT NULL — mensagem detalhada do evento
        - link TEXT nullable — rota frontend para navegar ao item
        - lida BOOLEAN NOT NULL DEFAULT FALSE
        - lida_em TIMESTAMPTZ nullable
        - deletada BOOLEAN NOT NULL DEFAULT FALSE — soft delete
        - deletada_em TIMESTAMPTZ nullable
        - metadata JSONB NOT NULL DEFAULT '{}' — dados extras estruturados
        - created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

    3. Ativa Row Level Security em notifications.
       Política: user_id = current_setting('app.user_id', true)::uuid
       (Isolamento por usuário — notificações são privadas de cada user.)

    4. Cria índices para performance:
        - idx_notifications_user_unread (user_id, lida) WHERE lida=FALSE AND deletada=FALSE
          Índice parcial para badge de não lidas — consulta de alta frequência.
        - idx_notifications_user_created (user_id, created_at)
          Índice composto para listagem paginada por data decrescente.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2024-01-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Adiciona 'check_campaign_alerts' ao ENUM task_queue_type
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TYPE task_queue_type ADD VALUE IF NOT EXISTS 'check_campaign_alerts'"
    )

    # -----------------------------------------------------------------------
    # 2. Cria o ENUM notification_tipo (idempotente via DO $$)
    # -----------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_tipo') THEN
                CREATE TYPE notification_tipo AS ENUM ('campanha_encerrada', 'relatorio_pronto', 'nova_denuncia', 'plano_vencendo', 'analise_ia_concluida', 'checklist_concluido', 'taxa_resposta_baixa');
            END IF;
        END$$;
    """)

    # -----------------------------------------------------------------------
    # 3. Cria tabela notifications
    # -----------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tipo",
            postgresql.ENUM(
                "campanha_encerrada",
                "relatorio_pronto",
                "nova_denuncia",
                "plano_vencendo",
                "analise_ia_concluida",
                "checklist_concluido",
                "taxa_resposta_baixa",
                name="notification_tipo",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("titulo", sa.Text, nullable=False),
        sa.Column("mensagem", sa.Text, nullable=False),
        sa.Column("link", sa.Text, nullable=True),
        sa.Column("lida", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("lida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deletada", sa.Boolean, nullable=False, server_default="FALSE"),
        sa.Column("deletada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # -----------------------------------------------------------------------
    # 4. Índices de performance
    # -----------------------------------------------------------------------

    # Índice para company_id (listagens admin futuras)
    op.create_index(
        "ix_notifications_company_id",
        "notifications",
        ["company_id"],
    )

    # Índice para user_id (listagem básica)
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
    )

    # Índice parcial para badge de não lidas — consulta de alta frequência
    op.create_index(
        "idx_notifications_user_unread",
        "notifications",
        ["user_id", "lida"],
        postgresql_where=sa.text("lida = FALSE AND deletada = FALSE"),
    )

    # Índice composto para listagem paginada por data
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )

    # -----------------------------------------------------------------------
    # 5. Ativa Row Level Security
    # -----------------------------------------------------------------------
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")

    # Política por user_id — notificações são privadas de cada usuário.
    # current_setting com missing_ok=true evita erro se a variável não estiver setada.
    # Quando app.user_id não está configurado, a função retorna NULL e a policy
    # bloqueia o acesso (nenhuma linha retornada) — comportamento seguro por padrão.
    op.execute(
        """
        CREATE POLICY rls_notifications ON notifications
            USING (
                user_id = current_setting('app.user_id', true)::uuid
            )
        """
    )

    # Política extra para bypass por superuser/service role (workers)
    op.execute(
        """
        CREATE POLICY rls_notifications_bypass ON notifications
            AS PERMISSIVE
            FOR ALL
            TO postgres
            USING (true)
        """
    )


def downgrade() -> None:
    # Remove políticas e RLS
    op.execute("DROP POLICY IF EXISTS rls_notifications_bypass ON notifications")
    op.execute("DROP POLICY IF EXISTS rls_notifications ON notifications")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY")

    # Remove índices
    op.drop_index("idx_notifications_user_created", table_name="notifications")
    op.drop_index("idx_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_company_id", table_name="notifications")

    # Remove tabela
    op.drop_table("notifications")

    # Remove ENUM
    postgresql.ENUM(name="notification_tipo").drop(op.get_bind(), checkfirst=True)

    # Nota: valores de ENUM não podem ser removidos no PostgreSQL sem recriar o tipo.
    # 'check_campaign_alerts' permanece no ENUM task_queue_type após downgrade.
