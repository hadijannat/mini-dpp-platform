"""
FastAPI application entry point.
Configures middleware, routers, and lifecycle events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import close_db, init_db
from app.modules.connectors.router import router as connectors_router
from app.modules.dpps.router import router as dpps_router
from app.modules.export.router import router as export_router
from app.modules.masters.router import router as masters_router
from app.modules.policies.router import router as policies_router
from app.modules.qr.router import router as qr_router
from app.modules.settings.router import router as settings_router
from app.modules.templates.router import router as templates_router
from app.modules.tenants.router import router as tenants_router

# Configure logging before anything else
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events for database connections,
    cache initialization, and other resources.
    """
    settings = get_settings()
    logger.info(
        "starting_application",
        environment=settings.environment,
        version=settings.version,
    )

    # Startup: Initialize connections
    await init_db()
    logger.info("database_initialized")

    yield

    # Shutdown: Clean up connections
    await close_db()
    logger.info("application_shutdown_complete")


def create_application() -> FastAPI:
    """
    Application factory function.

    Creates and configures the FastAPI application with all middleware,
    routers, and settings applied.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        lifespan=lifespan,
    )

    # ==========================================================================
    # Middleware Configuration
    # ==========================================================================

    # CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    )

    # Gzip compression for responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ==========================================================================
    # Router Registration
    # ==========================================================================

    # Health check endpoint (no auth required)
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        return {"status": "healthy", "version": settings.version}

    # API v1 routers
    app.include_router(
        tenants_router,
        prefix=f"{settings.api_v1_prefix}/tenants",
        tags=["Tenants"],
    )
    app.include_router(
        templates_router,
        prefix=f"{settings.api_v1_prefix}/templates",
        tags=["Templates"],
    )
    tenant_prefix = f"{settings.api_v1_prefix}/tenants/{{tenant_slug}}"
    app.include_router(
        dpps_router,
        prefix=f"{tenant_prefix}/dpps",
        tags=["DPPs"],
    )
    app.include_router(
        masters_router,
        prefix=f"{tenant_prefix}/masters",
        tags=["DPP Masters"],
    )
    app.include_router(
        policies_router,
        prefix=f"{tenant_prefix}/policies",
        tags=["Policies"],
    )
    app.include_router(
        connectors_router,
        prefix=f"{tenant_prefix}/connectors",
        tags=["Connectors"],
    )
    app.include_router(
        export_router,
        prefix=f"{tenant_prefix}/export",
        tags=["Export"],
    )
    app.include_router(
        qr_router,
        prefix=f"{tenant_prefix}/qr",
        tags=["QR Codes"],
    )
    app.include_router(
        settings_router,
        prefix=f"{settings.api_v1_prefix}/admin/settings",
        tags=["Settings"],
    )

    return app


# Application instance
app = create_application()
