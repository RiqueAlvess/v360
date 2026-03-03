"""Configuração do ambiente Alembic para migrations assíncronas."""

import asyncio
from logging.config import fileConfig
from typing import Optional

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.infrastructure.database.session import Base
from src.shared.config import settings

# Carregar todos os modelos para que o Alembic os detecte automaticamente
# Adicione os imports de models aqui conforme forem criados:
# from src.infrastructure.database.models import *  # noqa: F401, F403

# Configuração do Alembic
config = context.config

# Injetar DATABASE_URL das settings (ignora o valor no alembic.ini)
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

# Configurar logging a partir do alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata para autogenerate de migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Executa migrations em modo offline (sem conexão ativa).

    Gera o SQL para execução manual — útil para auditoria ou ambientes
    sem acesso direto ao banco.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Executa as migrations com uma conexão ativa."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Executa migrations de forma assíncrona (modo online)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Ponto de entrada para migrations online."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
