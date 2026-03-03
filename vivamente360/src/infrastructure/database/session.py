"""Configuração do engine assíncrono e sessão do SQLAlchemy."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.shared.config import settings


class Base(DeclarativeBase):
    """Classe base para todos os modelos ORM SQLAlchemy."""

    pass


def create_engine() -> AsyncEngine:
    """Cria e retorna o engine assíncrono do SQLAlchemy."""
    return create_async_engine(
        str(settings.DATABASE_URL),
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,  # Valida conexões antes do uso
    )


engine: AsyncEngine = create_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Dependency FastAPI — fornece uma sessão de banco por request.

    Uso nos routers:
        async def endpoint(db: AsyncSession = Depends(get_db)) -> ...:
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
