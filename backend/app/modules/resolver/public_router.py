"""Public (unauthenticated) GS1 Digital Link resolution endpoints.

Resolves GS1 Digital Link URIs to DPP endpoints via RFC 9264 Linkset
responses or HTTP 307 redirects, depending on content negotiation.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import DbSession
from app.modules.resolver.schemas import LinkType, ResolverDescriptionResponse
from app.modules.resolver.service import ResolverService

logger = get_logger(__name__)

router = APIRouter()


def _wants_linkset(request: Request) -> bool:
    """Check if the client prefers RFC 9264 linkset JSON."""
    accept = request.headers.get("accept", "")
    return "application/linkset+json" in accept


def _build_anchor(request: Request, identifier: str) -> str:
    """Build the anchor URI for linkset responses."""
    settings = get_settings()
    base = settings.resolver_base_url.rstrip("/") if settings.resolver_base_url else ""
    if base:
        return f"{base}/{identifier}"
    return str(request.url).split("?")[0]


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


async def _resolve(
    identifier: str,
    request: Request,
    db: DbSession,
    link_type_filter: str | None,
) -> Any:
    """Core resolution logic with content negotiation."""
    service = ResolverService(db)
    links = await service.resolve(identifier, link_type_filter=link_type_filter)

    if not links:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resolver links found for this identifier",
        )

    if _wants_linkset(request):
        anchor = _build_anchor(request, identifier)
        linkset = ResolverService.build_linkset(links, anchor)
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
    allowed_hosts = (
        list(raw_allowlist)
        if isinstance(raw_allowlist, (list, tuple, set))
        else []
    )
    if (
        getattr(redirect_link, "managed_by_system", False)
        and allowed_hosts
        and (parsed.hostname or "") not in allowed_hosts
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Managed redirect target host is not allowed",
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
async def resolver_description() -> ResolverDescriptionResponse:
    """GS1 resolver description document."""
    settings = get_settings()
    base_url = settings.resolver_base_url or ""
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
