import asyncio
import os
import sys
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Garantir que o pacote 'src' seja importável a partir deste arquivo.
# O alembic é executado no diretório vivamente360/, então src/ já está no path.
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Importar todos os models para registrá-los no metadata do Base.
# SEM este import, o autogenerate não detecta alterações nos models.
# ---------------------------------------------------------------------------
from src.infrastructure.database.models import Base  # noqa: E402
from src.shared.config import settings  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata para o autogenerate comparar com o schema do banco
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa migrations em modo 'offline' (sem conexão com o banco).

    Útil para gerar scripts SQL sem precisar de uma instância PostgreSQL ativa.
    """
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        render_as_batch=False,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Configura o contexto Alembic e executa as migrations na conexão fornecida."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        render_as_batch=False,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Cria o engine async e executa as migrations de forma assíncrona."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,  # NullPool para migrations — sem pool persistente
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point para execução online (padrão) — usa asyncio.run."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
