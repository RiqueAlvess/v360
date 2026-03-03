from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.shared.config import settings
from src.shared.exceptions import DomainException


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: expor engine e session factory centralizados via app.state
    from src.infrastructure.database.session import AsyncSessionLocal, engine

    app.state.engine = engine
    app.state.session_factory = AsyncSessionLocal

    yield

    # Shutdown: liberar pool de conexões
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Plataforma de avaliação 360 graus para o mercado B2B",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global domain exception handler
    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "version": settings.APP_VERSION}

    # Register routers
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    from src.presentation.routers.auth_router import router as auth_router
    from src.presentation.routers.campaign_router import router as campaign_router
    from src.presentation.routers.checklist_router import router as checklist_router
    from src.presentation.routers.dashboard_router import router as dashboard_router
    from src.presentation.routers.email_router import router as email_router
    from src.presentation.routers.survey_response_router import (
        router as survey_response_router,
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(campaign_router, prefix="/api/v1")
    app.include_router(checklist_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(email_router, prefix="/api/v1")
    app.include_router(survey_response_router, prefix="/api/v1")


app: FastAPI = create_app()
