"""Ponto de entrada da aplicação VIVAMENTE 360º.

Configura:
- FastAPI com metadata e docs
- CORS para origens permitidas
- Lifespan para gerenciamento do pool de conexão
- Handlers globais de exceções de domínio
- Roteadores da aplicação
- Endpoint /health para health check
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infrastructure.database.session import engine
from src.shared.config import settings
from src.shared.exceptions import (
    BaseAppException,
    ConflictError,
    DomainException,
    ForbiddenError,
    InfrastructureException,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)

# Mapeamento de exceção → código HTTP
_EXCEPTION_STATUS_MAP: dict[type[BaseAppException], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    ValidationError: 422,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    RateLimitError: 429,
    InfrastructureException: 503,
    DomainException: 400,
    BaseAppException: 500,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Gerencia o ciclo de vida da aplicação.

    - Startup: valida conectividade com o banco de dados.
    - Shutdown: fecha o pool de conexões graciosamente.
    """
    # Startup — testar pool de conexão
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

    yield

    # Shutdown — fechar pool
    await engine.dispose()


def create_application() -> FastAPI:
    """Factory da aplicação FastAPI."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "API REST da plataforma VIVAMENTE 360º — "
            "avaliação psicossocial B2B com arquitetura API-first."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Handlers de Exceção ────────────────────────────────────────────────
    @app.exception_handler(BaseAppException)
    async def app_exception_handler(
        request: Request, exc: BaseAppException
    ) -> JSONResponse:
        """Converte exceções de domínio em respostas HTTP padronizadas."""
        status_code = 500
        for exc_type, code in _EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break

        return JSONResponse(
            status_code=status_code,
            content=exc.to_dict(),
        )

    # ── Routers ───────────────────────────────────────────────────────────
    # Os routers serão adicionados aqui conforme os blueprints forem implementados
    # Exemplo: app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    # ── Health Check ──────────────────────────────────────────────────────
    @app.get(
        "/health",
        tags=["system"],
        summary="Health check da API",
        response_description="Status da aplicação",
    )
    async def health_check() -> dict[str, str]:
        """Verifica se a API está operacional.

        Retorna status e versão da aplicação.
        """
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
        }

    return app


app: FastAPI = create_application()
