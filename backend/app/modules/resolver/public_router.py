"""Public (unauthenticated) GS1 Digital Link resolution endpoints.

Resolves GS1 Digital Link URIs to DPP endpoints via RFC 9264 Linkset
responses or HTTP 307 redirects, depending on content negotiation.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import DbSession
from app.modules.resolver.schemas import LinkType, ResolverDescriptionResponse
from app.modules.resolver.service import ResolverService
from app.modules.tenant_domains.service import TenantDomainError, TenantDomainService

logger = get_logger(__name__)

router = APIRouter()


def _wants_linkset(request: Request) -> bool:
    """Check if the client prefers RFC 9264 linkset JSON."""
    accept = request.headers.get("accept", "")
    return "application/linkset+json" in accept


def _request_from_trusted_proxy(request: Request) -> bool:
    settings = get_settings()
    trusted_proxy_cidrs = getattr(settings, "trusted_proxy_cidrs", [])
    if not isinstance(trusted_proxy_cidrs, (list, tuple, set)):
        trusted_proxy_cidrs = []
    connection_ip = request.client.host if request.client else ""
    if not connection_ip:
        return False
    try:
        addr = ipaddress.ip_address(connection_ip)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs)


def _split_header_first(value: str | None) -> str:
    if not value:
        return ""
    return value.split(",")[0].strip()


def _external_host(request: Request) -> str:
    trusted_proxy = _request_from_trusted_proxy(request)
    if trusted_proxy:
        forwarded = _split_header_first(request.headers.get("x-forwarded-host"))
        if forwarded:
            return forwarded.split(":")[0].strip().lower().rstrip(".")
    host = _split_header_first(request.headers.get("host")) or request.url.netloc
    return host.split(":")[0].strip().lower().rstrip(".")


def _external_scheme(request: Request) -> str:
    trusted_proxy = _request_from_trusted_proxy(request)
    if trusted_proxy:
        forwarded = _split_header_first(request.headers.get("x-forwarded-proto"))
        if forwarded:
            return forwarded.lower()
    return request.url.scheme


def _external_base(request: Request) -> str:
    return f"{_external_scheme(request)}://{_external_host(request)}"


def _build_anchor(request: Request) -> str:
    return f"{_external_base(request)}{request.url.path}"


def _is_legacy_resolver_path(request: Request) -> bool:
    settings = get_settings()
    raw_prefix = getattr(settings, "api_v1_prefix", "/api/v1")
    api_v1_prefix = raw_prefix if isinstance(raw_prefix, str) and raw_prefix else "/api/v1"
    legacy_prefixes = (f"{api_v1_prefix}/resolve", "/resolve")
    return any(request.url.path.startswith(prefix) for prefix in legacy_prefixes)


async def _enable_public_lookup_role_if_configured(db: DbSession) -> None:
    settings = get_settings()
    role = getattr(settings, "db_admin_role", None)
    if not isinstance(role, str):
        return
    role = role.strip()
    if not role:
        return
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
        return
    await db.execute(text(f'SET LOCAL ROLE "{role}"'))


@router.get("/01/{gtin}")
async def resolve_gtin(
    gtin: str,
    request: Request,
    db: DbSession,
    linkType: str | None = Query(default=None, description="Filter by link relation type"),
) -> Any:
    """Resolve by GTIN only."""
    identifier = f"01/{gtin}"
    return await _resolve(identifier, request, db, linkType)


@router.get("/01/{gtin}/21/{serial}")
async def resolve_gtin_serial(
    gtin: str,
    serial: str,
    request: Request,
    db: DbSession,
    linkType: str | None = Query(default=None, description="Filter by link relation type"),
) -> Any:
    """Resolve by GTIN + serial number."""
    identifier = f"01/{gtin}/21/{serial}"
    return await _resolve(identifier, request, db, linkType)


@router.get("/01/{gtin}/10/{lot}")
async def resolve_gtin_lot(
    gtin: str,
    lot: str,
    request: Request,
    db: DbSession,
    linkType: str | None = Query(default=None, description="Filter by link relation type"),
) -> Any:
    """Resolve by GTIN + lot number."""
    identifier = f"01/{gtin}/10/{lot}"
    return await _resolve(identifier, request, db, linkType)


@router.get("/01/{gtin}/21/{serial}/10/{lot}")
async def resolve_gtin_serial_lot(
    gtin: str,
    serial: str,
    lot: str,
    request: Request,
    db: DbSession,
    linkType: str | None = Query(default=None, description="Filter by link relation type"),
) -> Any:
    """Resolve by GTIN + serial + lot."""
    identifier = f"01/{gtin}/21/{serial}/10/{lot}"
    return await _resolve(identifier, request, db, linkType)


@router.get("/00/{sscc}")
async def resolve_sscc(
    sscc: str,
    request: Request,
    db: DbSession,
    linkType: str | None = Query(default=None, description="Filter by link relation type"),
) -> Any:
    """Resolve by SSCC."""
    identifier = f"00/{sscc}"
    return await _resolve(identifier, request, db, linkType)


async def _resolve(
    identifier: str,
    request: Request,
    db: DbSession,
    link_type_filter: str | None,
) -> Any:
    """Core resolution logic with content negotiation."""
    await _enable_public_lookup_role_if_configured(db)

    tenant_id = None
    host = _external_host(request)
    if not _is_legacy_resolver_path(request):
        try:
            tenant_id = await TenantDomainService(db).resolve_active_tenant_by_hostname(host)
        except TenantDomainError:
            tenant_id = None
        if tenant_id is None:
            logger.info(
                "resolver_host_unmapped",
                host=host,
                identifier=identifier,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active tenant domain found for host",
            )

    service = ResolverService(db)
    links = await service.resolve(
        identifier,
        link_type_filter=link_type_filter,
        tenant_id=tenant_id,
    )

    if not links:
        logger.info(
            "resolver_not_found",
            host=host,
            identifier=identifier,
            tenant_id=str(tenant_id) if tenant_id else None,
            link_type_filter=link_type_filter,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resolver links found for this identifier",
        )

    if _wants_linkset(request):
        anchor = _build_anchor(request)
        linkset = ResolverService.build_linkset(links, anchor)
        logger.info(
            "resolver_linkset_served",
            host=host,
            identifier=identifier,
            tenant_id=str(tenant_id) if tenant_id else None,
            link_count=len(links),
        )
        return JSONResponse(
            content=linkset,
            media_type="application/linkset+json",
            headers={"Cache-Control": "public, max-age=60, stale-while-revalidate=300"},
        )

    # Default: HTTP 307 redirect to highest-priority DPP link
    dpp_links = [lnk for lnk in links if lnk.link_type == LinkType.HAS_DPP.value]
    redirect_link = dpp_links[0] if dpp_links else links[0]

    # Validate redirect target to prevent open redirect attacks
    parsed = urlparse(redirect_link.href)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid redirect target",
        )
    settings = get_settings()
    raw_allowlist = getattr(settings, "carrier_resolver_allowed_hosts_all", [])
    allowed_hosts = list(raw_allowlist) if isinstance(raw_allowlist, (list, tuple, set)) else []
    request_host = _external_host(request)
    target_host = (parsed.hostname or "").lower()
    if (
        getattr(redirect_link, "managed_by_system", False)
        and allowed_hosts
        and target_host not in allowed_hosts
        and target_host != request_host
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Managed redirect target host is not allowed",
        )

    logger.info(
        "resolver_redirect_served",
        host=host,
        identifier=identifier,
        tenant_id=str(tenant_id) if tenant_id else None,
        href=redirect_link.href,
    )
    return RedirectResponse(
        url=redirect_link.href,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get(
    "/.well-known/gs1resolver",
    response_model=ResolverDescriptionResponse,
)
async def resolver_description(
    request: Request,
    db: DbSession,
) -> ResolverDescriptionResponse:
    """GS1 resolver description document."""
    await _enable_public_lookup_role_if_configured(db)
    base_url = _external_base(request)
    if not _is_legacy_resolver_path(request):
        try:
            tenant_id = await TenantDomainService(db).resolve_active_tenant_by_hostname(
                _external_host(request)
            )
        except TenantDomainError:
            tenant_id = None
        if tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active tenant domain found for host",
            )
    return ResolverDescriptionResponse(
        name="Mini DPP Platform GS1 Digital Link Resolver",
        resolverRoot=base_url,
        supportedLinkTypes=[
            {
                "namespace": "iec61406" if lt.value.startswith("iec61406:") else "gs1",
                "prefix": "iec61406:" if lt.value.startswith("iec61406:") else "gs1:",
                "type": lt.value,
            }
            for lt in LinkType
        ],
        supportedContextValuesEnumerated=["en", "de", "fr"],
    )
