from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.shared.config import settings
from src.shared.exceptions import DomainException

# Instância global do rate limiter — chave por IP remoto
limiter: Limiter = Limiter(key_func=get_remote_address)


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

    # Registrar o limiter no state da app (necessário para slowapi)
    app.state.limiter = limiter

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware — aplica limites globais por IP
    app.add_middleware(SlowAPIMiddleware)

    # Handler HTTP 429 para rate limit excedido
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

    # ── SQLAdmin ─────────────────────────────────────────────────────────────
    # Painel global de administração em /sqladmin
    # Autenticação própria — completamente separada do JWT da aplicação
    from sqladmin import Admin
    from sqladmin.authentication import AuthenticationBackend
    from starlette.requests import Request as StarletteRequest

    from src.infrastructure.admin.views import (
        CampaignAdmin,
        CompanyAdmin,
        UserAdmin,
    )

    class _SuperAdminAuth(AuthenticationBackend):
        """Backend de autenticação para o painel SQLAdmin.

        Valida credenciais via SQLADMIN_USERNAME e SQLADMIN_PASSWORD do .env.
        Mantém sessão via cookie assinado com SQLADMIN_SECRET_KEY.
        """

        async def login(self, request: StarletteRequest) -> bool:
            form = await request.form()
            username: str = str(form.get("username", ""))
            password: str = str(form.get("password", ""))
            if (
                username == settings.SQLADMIN_USERNAME
                and password == settings.SQLADMIN_PASSWORD
            ):
                request.session.update({"sqladmin_auth": True})
                return True
            return False

        async def logout(self, request: StarletteRequest) -> bool:
            request.session.clear()
            return True

        async def authenticate(self, request: StarletteRequest) -> bool:
            return bool(request.session.get("sqladmin_auth", False))

    # engine é o AsyncEngine já criado no app — reutilizar, não criar novo
    from src.infrastructure.database.session import engine as _db_engine

    _admin = Admin(
        app,
        engine=_db_engine,
        authentication_backend=_SuperAdminAuth(
            secret_key=settings.SQLADMIN_SECRET_KEY
        ),
        title="VIVAMENTE 360° — Admin",
        base_url="/sqladmin",
    )
    _admin.add_view(CompanyAdmin)
    _admin.add_view(UserAdmin)
    _admin.add_view(CampaignAdmin)

    return app


def _register_routers(app: FastAPI) -> None:
    from src.presentation.routers.action_plan_router import router as action_plan_router
    from src.presentation.routers.ai_analysis_router import router as ai_analysis_router
    from src.presentation.routers.auth_router import router as auth_router
    from src.presentation.routers.campaign_router import router as campaign_router
    from src.presentation.routers.checklist_router import router as checklist_router
    from src.presentation.routers.dashboard_router import router as dashboard_router
    from src.presentation.routers.email_router import router as email_router
    from src.presentation.routers.file_router import router as file_router
    from src.presentation.routers.notifications_router import (
        router as notifications_router,
    )
    from src.presentation.routers.survey_response_router import (
        router as survey_response_router,
    )
    from src.presentation.routers.whistleblower_router import (
        admin_router as whistleblower_admin_router,
        public_router as whistleblower_public_router,
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(campaign_router, prefix="/api/v1")
    app.include_router(checklist_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(email_router, prefix="/api/v1")
    app.include_router(survey_response_router, prefix="/api/v1")
    app.include_router(action_plan_router, prefix="/api/v1")
    app.include_router(ai_analysis_router, prefix="/api/v1")
    # Módulo 07 — Canal de Denúncias Anônimo (NR-1 / Portaria MTE 1.419/2024)
    app.include_router(whistleblower_public_router, prefix="/api/v1")
    app.include_router(whistleblower_admin_router, prefix="/api/v1")
    # Módulo 08 — Notificações In-App
    app.include_router(notifications_router, prefix="/api/v1")
    # Módulo Storage — Upload de evidências (Cloudflare R2)
    app.include_router(file_router, prefix="/api/v1")


app: FastAPI = create_app()
