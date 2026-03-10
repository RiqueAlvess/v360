"""rls_policies

Ativa Row Level Security nas tabelas de negócio e cria as políticas de
isolamento multi-tenant. Cria a role app_user com permissões restritas.

Depende de: 3a8f9b2c1d4e (initial_schema)

Revision ID: 5e6f7a8b9c0d
Revises: 3a8f9b2c1d4e
Create Date: 2024-01-01 00:01:00.000000

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "5e6f7a8b9c0d"
down_revision: Union[str, None] = "3a8f9b2c1d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Caminho para o arquivo SQL com as políticas (relativo ao diretório do env.py)
_RLS_SQL_PATH = Path(__file__).parent.parent / "rls_policies.sql"


def _split_sql_statements(sql_content: str) -> list[str]:
    """Split SQL content into individual statements for asyncpg compatibility.

    asyncpg does not support multiple statements in a single prepared statement.
    This splits on semicolons while respecting DO $$ ... $$ blocks.
    """
    statements: list[str] = []
    current = ""

    for line in sql_content.splitlines():
        stripped = line.strip()
        # Skip pure comment lines and empty lines
        if stripped.startswith("--") or not stripped:
            continue
        current += line + "\n"

        # If we're inside a DO $$ block, wait for the closing $$;
        if "DO $$" in current or "DO  $$" in current:
            if current.rstrip().endswith("$$;"):
                statements.append(current.strip())
                current = ""
            continue

        # Normal statement ending with semicolon
        if stripped.endswith(";"):
            statements.append(current.strip())
            current = ""

    if current.strip():
        statements.append(current.strip())

    return [s for s in statements if s]


def upgrade() -> None:
    sql_content = _RLS_SQL_PATH.read_text(encoding="utf-8")
    for statement in _split_sql_statements(sql_content):
        op.execute(text(statement))


def downgrade() -> None:
    # Revogar permissões e remover políticas
    op.execute(text("DROP POLICY IF EXISTS tenant_isolation_survey_responses ON survey_responses"))
    op.execute(text("DROP POLICY IF EXISTS tenant_isolation_invitations ON invitations"))
    op.execute(text("DROP POLICY IF EXISTS tenant_isolation_campaigns ON campaigns"))
    op.execute(text("DROP POLICY IF EXISTS tenant_isolation_companies ON companies"))

    op.execute(text("ALTER TABLE survey_responses DISABLE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE invitations DISABLE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE campaigns DISABLE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE companies DISABLE ROW LEVEL SECURITY"))

    # Revogar permissões da role app_user
    op.execute(text("REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM app_user"))
    op.execute(text("REVOKE USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public FROM app_user"))
    op.execute(text("REVOKE USAGE ON SCHEMA public FROM app_user"))
