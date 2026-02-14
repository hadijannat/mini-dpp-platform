"""
FastAPI application entry point.
Configures middleware, routers, and lifecycle events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import RateLimitMiddleware, close_redis, get_redis
from app.core.security.abac import close_opa_client
from app.db.session import close_db, get_db_session, init_db
from app.modules.activity.router import router as activity_router
from app.modules.audit.router import router as audit_router
from app.modules.cirpass.public_router import router as public_cirpass_router
from app.modules.compliance.router import router as compliance_router
from app.modules.connectors.router import router as connectors_router
from app.modules.credentials.public_router import router as public_credentials_router
from app.modules.credentials.router import router as credentials_router
from app.modules.data_carriers.router import router as data_carriers_router
from app.modules.dataspace.router import router as dataspace_router
from app.modules.digital_thread.router import router as digital_thread_router
from app.modules.dpps.public_router import router as public_dpps_router
from app.modules.dpps.router import router as dpps_router
from app.modules.epcis.public_router import router as public_epcis_router
from app.modules.epcis.router import router as epcis_router
from app.modules.export.router import router as export_router
from app.modules.lab.router import router as lab_router
from app.modules.lca.router import router as lca_router
from app.modules.masters.router import router as masters_router
from app.modules.onboarding.role_request_router import router as role_request_router
from app.modules.onboarding.router import router as onboarding_router
from app.modules.policies.router import router as policies_router
from app.modules.qr.router import router as qr_router
from app.modules.registry.public_router import router as public_registry_router
from app.modules.registry.router import router as registry_router
from app.modules.resolver.public_router import router as public_resolver_router
from app.modules.resolver.router import router as resolver_router
from app.modules.settings.router import router as settings_router
from app.modules.shares.router import router as shares_router
from app.modules.templates.router import router as templates_router
from app.modules.tenants.router import router as tenants_router
from app.modules.webhooks.router import router as webhooks_router

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
    await close_opa_client()
    await close_redis()
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
        docs_url=None,  # Custom docs endpoint below
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        lifespan=lifespan,
    )

    # Custom Swagger UI endpoint — FastAPI's built-in version has a timing
    # issue with swagger-ui v5 where the inline init script fires before the
    # bundle's internal React setup completes, producing a blank page. This
    # defers initialization to window.onload to guarantee readiness.
    @app.get(f"{settings.api_v1_prefix}/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
<link type="text/css" rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<title>{settings.project_name} - Swagger UI</title>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
window.onload = function() {{
    SwaggerUIBundle({{
        url: "{settings.api_v1_prefix}/openapi.json",
        dom_id: "#swagger-ui",
        layout: "BaseLayout",
        deepLinking: true,
        showExtensions: true,
        showCommonExtensions: true,
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
        ]
    }});
}};
</script>
</body>
</html>""")

    # ==========================================================================
    # Middleware Configuration
    # ==========================================================================

    # CORS middleware for frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
    )

    # Rate limiting (skipped in development)
    app.add_middleware(RateLimitMiddleware)

    # Security headers on every response
    app.add_middleware(SecurityHeadersMiddleware)

    # Gzip compression for responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ==========================================================================
    # Router Registration
    # ==========================================================================

    # Health check endpoint (no auth required)
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, object]:
        checks: dict[str, str] = {}

        # Probe PostgreSQL
        try:
            async for session in get_db_session():
                await session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception:
            checks["db"] = "unavailable"

        # Probe Redis
        try:
            r = await get_redis()
            if r is not None:
                await r.ping()  # type: ignore[misc,unused-ignore]
                checks["redis"] = "ok"
            else:
                checks["redis"] = "unavailable"
        except Exception:
            checks["redis"] = "unavailable"

        # Probe EDC (if configured)
        if settings.edc_management_url:
            try:
                from app.modules.connectors.edc.client import (
                    EDCConfig,
                    EDCManagementClient,
                )
                from app.modules.connectors.edc.health import check_edc_health

                edc_cfg = EDCConfig(
                    management_url=settings.edc_management_url,
                    api_key=settings.edc_management_api_key,
                )
                client = EDCManagementClient(edc_cfg)
                try:
                    edc_result = await check_edc_health(client)
                    checks["edc"] = edc_result.get("status", "unavailable")
                finally:
                    await client.close()
            except Exception:
                checks["edc"] = "unavailable"

        overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
        return {"status": overall, "version": settings.version, "checks": checks}

    # Public API (no authentication required)
    app.include_router(
        public_dpps_router,
        prefix=f"{settings.api_v1_prefix}/public",
        tags=["Public DPPs"],
    )
    app.include_router(
        public_epcis_router,
        prefix=f"{settings.api_v1_prefix}/public",
        tags=["Public EPCIS"],
    )
    app.include_router(
        public_registry_router,
        prefix=f"{settings.api_v1_prefix}/public",
        tags=["Public Registry"],
    )
    app.include_router(
        public_resolver_router,
        prefix=f"{settings.api_v1_prefix}/resolve",
        tags=["GS1 Resolver"],
    )
    app.include_router(
        public_credentials_router,
        prefix=f"{settings.api_v1_prefix}/public",
        tags=["Public Credentials"],
    )
    app.include_router(
        public_cirpass_router,
        prefix=f"{settings.api_v1_prefix}/public",
        tags=["Public CIRPASS"],
    )
    app.include_router(
        lab_router,
        prefix=f"{settings.api_v1_prefix}/lab",
        tags=["Lab Sandbox"],
    )

    # Onboarding (authenticated, not tenant-scoped)
    app.include_router(
        onboarding_router,
        prefix=f"{settings.api_v1_prefix}/onboarding",
        tags=["Onboarding"],
    )

    # API v1 routers (authenticated)
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
        dataspace_router,
        prefix=f"{tenant_prefix}/dataspace",
        tags=["Dataspace"],
    )
    app.include_router(
        shares_router,
        prefix=f"{tenant_prefix}/shares",
        tags=["Resource Shares"],
    )
    app.include_router(
        activity_router,
        prefix=f"{tenant_prefix}/activity",
        tags=["Activity"],
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
        data_carriers_router,
        prefix=f"{tenant_prefix}/data-carriers",
        tags=["Data Carriers"],
    )
    app.include_router(
        settings_router,
        prefix=f"{settings.api_v1_prefix}/admin/settings",
        tags=["Settings"],
    )
    app.include_router(
        compliance_router,
        prefix=f"{tenant_prefix}/compliance",
        tags=["Compliance"],
    )
    app.include_router(
        audit_router,
        prefix=f"{settings.api_v1_prefix}/admin/audit",
        tags=["Audit"],
    )
    app.include_router(
        digital_thread_router,
        prefix=f"{tenant_prefix}/thread",
        tags=["Digital Thread"],
    )
    app.include_router(
        lca_router,
        prefix=f"{tenant_prefix}/lca",
        tags=["LCA"],
    )
    app.include_router(
        epcis_router,
        prefix=f"{tenant_prefix}/epcis",
        tags=["EPCIS"],
    )
    app.include_router(
        webhooks_router,
        prefix=f"{tenant_prefix}/webhooks",
        tags=["Webhooks"],
    )
    app.include_router(
        resolver_router,
        prefix=f"{tenant_prefix}/resolver",
        tags=["Resolver"],
    )
    app.include_router(
        registry_router,
        prefix=f"{tenant_prefix}/registry",
        tags=["Registry"],
    )
    app.include_router(
        credentials_router,
        prefix=f"{tenant_prefix}/credentials",
        tags=["Credentials"],
    )
    app.include_router(
        role_request_router,
        prefix=f"{tenant_prefix}/role-requests",
        tags=["Role Requests"],
    )

    # Prometheus metrics endpoint
    from prometheus_fastapi_instrumentator import Instrumentator

    instrumentator = Instrumentator().instrument(app)

    if settings.environment == "development" and not settings.metrics_auth_token:
        # Development: expose metrics without auth for convenience
        instrumentator.expose(app, endpoint="/metrics")
    else:
        # Production / when token is set: auth-gated metrics
        import hmac as _hmac

        from fastapi import Header, Response

        @app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint(
            authorization: str | None = Header(default=None),
        ) -> Response:
            if not settings.metrics_auth_token:
                # No token configured in production — hide the endpoint
                return Response(status_code=404)

            if not authorization or not authorization.startswith("Bearer "):
                return Response(status_code=401)

            provided = authorization.removeprefix("Bearer ")
            if not _hmac.compare_digest(provided, settings.metrics_auth_token):
                return Response(status_code=401)

            # Generate and return metrics
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

    return app


# Application instance
app = create_application()
