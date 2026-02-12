"""Tenant-scoped admin CRUD routes for GS1 Digital Link resolver."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.core.tenancy import TenantPublisher
from app.db.session import DbSession
from app.modules.resolver.schemas import (
    ResolverLinkCreate,
    ResolverLinkResponse,
    ResolverLinkUpdate,
)
from app.modules.resolver.service import ResolverService

router = APIRouter()


def _link_to_response(link: object) -> ResolverLinkResponse:
    """Convert ORM model to response schema."""
    from app.db.models import ResolverLink

    assert isinstance(link, ResolverLink)
    return ResolverLinkResponse(
        id=link.id,
        tenant_id=link.tenant_id,
        identifier=link.identifier,
        link_type=link.link_type,
        href=link.href,
        media_type=link.media_type,
        title=link.title,
        hreflang=link.hreflang,
        priority=link.priority,
        dpp_id=link.dpp_id,
        active=link.active,
        managed_by_system=link.managed_by_system,
        source_data_carrier_id=link.source_data_carrier_id,
        created_by_subject=link.created_by_subject,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.get("", response_model=list[ResolverLinkResponse])
async def list_resolver_links(
    db: DbSession,
    tenant: TenantPublisher,
    dpp_id: UUID | None = Query(default=None, description="Filter by DPP ID"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> list[ResolverLinkResponse]:
    """List resolver links for the tenant."""
    service = ResolverService(db)
    links = await service.list_links(
        tenant.tenant_id, dpp_id=dpp_id, active_only=False, limit=limit, offset=offset
    )
    return [_link_to_response(link) for link in links]


@router.post("", response_model=ResolverLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_resolver_link(
    body: ResolverLinkCreate,
    db: DbSession,
    tenant: TenantPublisher,
) -> ResolverLinkResponse:
    """Create a new resolver link."""
    service = ResolverService(db)
    link = await service.create_link(
        tenant_id=tenant.tenant_id,
        link_create=body,
        created_by=tenant.user.sub,
    )
    await db.commit()
    return _link_to_response(link)


@router.get("/{link_id}", response_model=ResolverLinkResponse)
async def get_resolver_link(
    link_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ResolverLinkResponse:
    """Get a specific resolver link."""
    service = ResolverService(db)
    link = await service.get_link(link_id, tenant.tenant_id)
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resolver link not found",
        )
    return _link_to_response(link)


@router.patch("/{link_id}", response_model=ResolverLinkResponse)
async def update_resolver_link(
    link_id: UUID,
    body: ResolverLinkUpdate,
    db: DbSession,
    tenant: TenantPublisher,
) -> ResolverLinkResponse:
    """Update a resolver link."""
    service = ResolverService(db)
    try:
        link = await service.update_link(link_id, tenant.tenant_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resolver link not found",
        )
    await db.commit()
    return _link_to_response(link)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resolver_link(
    link_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete a resolver link."""
    service = ResolverService(db)
    try:
        deleted = await service.delete_link(link_id, tenant.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resolver link not found",
        )
    await db.commit()
