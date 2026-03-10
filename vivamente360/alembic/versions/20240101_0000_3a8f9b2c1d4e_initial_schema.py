"""initial_schema

Cria todas as tabelas do schema central: companies, users, refresh_tokens,
campaigns, invitations, survey_responses, task_queue e email_logs.
Inclui tipos ENUM nativos do PostgreSQL e o índice composto da task_queue.

Revision ID: 3a8f9b2c1d4e
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3a8f9b2c1d4e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Definições de ENUM nativo PostgreSQL (usadas apenas no downgrade/drop)
# create_type=False evita que o SQLAlchemy tente criar o tipo via evento
# before_create ao referenciar este objeto por nome em qualquer contexto.
# ---------------------------------------------------------------------------
COMPANY_PLAN_ENUM = sa.Enum(
    "free", "basic", "professional", "enterprise",
    name="company_plan",
    create_type=False,
)
USER_ROLE_ENUM = sa.Enum(
    "admin", "manager", "respondent",
    name="user_role",
    create_type=False,
)
CAMPAIGN_STATUS_ENUM = sa.Enum(
    "draft", "active", "paused", "completed", "cancelled",
    name="campaign_status",
    create_type=False,
)
TASK_QUEUE_TYPE_ENUM = sa.Enum(
    "compute_scores", "send_email", "send_invitations", "generate_report",
    name="task_queue_type",
    create_type=False,
)
TASK_QUEUE_STATUS_ENUM = sa.Enum(
    "pending", "processing", "completed", "failed", "cancelled",
    name="task_queue_status",
    create_type=False,
)
EMAIL_LOG_STATUS_ENUM = sa.Enum(
    "pending", "sent", "failed", "bounced",
    name="email_log_status",
    create_type=False,
)


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Criar tipos ENUM nativos do PostgreSQL (idempotente via DO $$)
    # Usar DO $$ garante que o CREATE TYPE só ocorre se o tipo não existe,
    # independente do estado do banco — evita DuplicateObjectError no asyncpg.
    # -----------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'company_plan') THEN
                CREATE TYPE company_plan AS ENUM ('free', 'basic', 'professional', 'enterprise');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                CREATE TYPE user_role AS ENUM ('admin', 'manager', 'respondent');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'campaign_status') THEN
                CREATE TYPE campaign_status AS ENUM ('draft', 'active', 'paused', 'completed', 'cancelled');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_queue_type') THEN
                CREATE TYPE task_queue_type AS ENUM ('compute_scores', 'send_email', 'send_invitations', 'generate_report');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_queue_status') THEN
                CREATE TYPE task_queue_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled');
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'email_log_status') THEN
                CREATE TYPE email_log_status AS ENUM ('pending', 'sent', 'failed', 'bounced');
            END IF;
        END$$;
    """)

    # -----------------------------------------------------------------------
    # 2. companies — raiz do isolamento multi-tenant
    # -----------------------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("cnpj", sa.String(18), nullable=False),
        sa.Column(
            "plano",
            sa.Enum("free", "basic", "professional", "enterprise",
                    name="company_plan", create_type=False),
            nullable=False,
            server_default="free",
        ),
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
        sa.UniqueConstraint("cnpj", name="uq_companies_cnpj"),
    )

    # -----------------------------------------------------------------------
    # 3. users — email cifrado em repouso (AES-256-GCM)
    # -----------------------------------------------------------------------
    op.create_table(
        "users",
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
        sa.Column("email_hash", sa.String(64), nullable=False),
        sa.Column("email_criptografado", sa.LargeBinary, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "manager", "respondent",
                    name="user_role", create_type=False),
            nullable=False,
            server_default="respondent",
        ),
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
        sa.UniqueConstraint(
            "company_id", "email_hash", name="uq_users_company_email"
        ),
    )
    op.create_index("ix_users_email_hash", "users", ["email_hash"])
    op.create_index("ix_users_company_id", "users", ["company_id"])

    # -----------------------------------------------------------------------
    # 4. refresh_tokens — tokens persistidos para revogação imediata
    # -----------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revogado", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # -----------------------------------------------------------------------
    # 5. campaigns — campanhas de avaliação psicossocial
    # -----------------------------------------------------------------------
    op.create_table(
        "campaigns",
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
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "paused", "completed", "cancelled",
                    name="campaign_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("data_inicio", sa.Date, nullable=False),
        sa.Column("data_fim", sa.Date, nullable=False),
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
    op.create_index("ix_campaigns_company_id", "campaigns", ["company_id"])

    # -----------------------------------------------------------------------
    # 6. invitations — convites com Blind Drop (email cifrado)
    # -----------------------------------------------------------------------
    op.create_table(
        "invitations",
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
        sa.Column("email_criptografado", sa.LargeBinary, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "respondido", sa.Boolean, nullable=False, server_default=sa.text("false")
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
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index("ix_invitations_campaign_id", "invitations", ["campaign_id"])

    # -----------------------------------------------------------------------
    # 7. survey_responses — respostas anônimas (sem FK para invitation)
    # -----------------------------------------------------------------------
    op.create_table(
        "survey_responses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        # Sem FK para invitations — Blind Drop garante anonimato
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("respostas", postgresql.JSONB, nullable=False),
        sa.Column(
            "anonimizado", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_survey_responses_campaign_id", "survey_responses", ["campaign_id"]
    )

    # -----------------------------------------------------------------------
    # 8. task_queue — fila de tarefas assíncronas em PostgreSQL
    # -----------------------------------------------------------------------
    op.create_table(
        "task_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "tipo",
            sa.Enum(
                "compute_scores", "send_email", "send_invitations", "generate_report",
                name="task_queue_type", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", "cancelled",
                name="task_queue_status", create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("tentativas", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "agendado_para",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
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
    # Índice composto crítico para o worker: filtra pending e ordena por agendamento
    op.create_index(
        "ix_task_queue_status_agendado_para",
        "task_queue",
        ["status", "agendado_para"],
    )

    # -----------------------------------------------------------------------
    # 9. email_logs — auditoria de envios via EmailService
    # -----------------------------------------------------------------------
    op.create_table(
        "email_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("tipo", sa.String(100), nullable=False),
        sa.Column("destinatario_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "failed", "bounced",
                    name="email_log_status", create_type=False),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Dropar tabelas na ordem inversa (respeitar FKs)
    op.drop_table("email_logs")
    op.drop_index("ix_task_queue_status_agendado_para", table_name="task_queue")
    op.drop_table("task_queue")
    op.drop_index("ix_survey_responses_campaign_id", table_name="survey_responses")
    op.drop_table("survey_responses")
    op.drop_index("ix_invitations_campaign_id", table_name="invitations")
    op.drop_table("invitations")
    op.drop_index("ix_campaigns_company_id", table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_email_hash", table_name="users")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_table("users")
    op.drop_table("companies")

    # Dropar tipos ENUM após as tabelas
    EMAIL_LOG_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    TASK_QUEUE_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    TASK_QUEUE_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
    CAMPAIGN_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    USER_ROLE_ENUM.drop(op.get_bind(), checkfirst=True)
    COMPANY_PLAN_ENUM.drop(op.get_bind(), checkfirst=True)
