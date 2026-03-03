from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.shared.config import settings

# Engine com pool configurado via settings — instância única para toda a aplicação
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # valida conexões antes de uso
)

# Session factory assíncrona — expire_on_commit=False evita lazy loads após commit
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependência FastAPI que fornece uma AsyncSession por request.

    A sessão é automaticamente fechada ao final do request.
    Commit e rollback são responsabilidade da camada de serviço.
    """
    async with AsyncSessionLocal() as session:
        yield session
