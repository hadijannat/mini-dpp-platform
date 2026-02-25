"""Public (unauthenticated) API for reading EPCIS events on published DPPs.

EU ESPR requires published DPPs to be accessible without authentication.
This router exposes supply-chain traceability events for published DPPs only.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.db.models import DPP, DPPStatus, EPCISEvent, Tenant, TenantStatus
from app.db.session import DbSession

from .schemas import PublicEPCISEventResponse, PublicEPCISQueryResponse

router = APIRouter()

MAX_PUBLIC_EVENTS = 100


async def _resolve_tenant(db: DbSession, tenant_slug: str) -> Tenant:
    """Look up an active tenant by slug (no auth required)."""
    result = await db.execute(
        select(Tenant).where(
            Tenant.slug == tenant_slug.strip().lower(),
            Tenant.status == TenantStatus.ACTIVE,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )
    return tenant


@router.get(
    "/{tenant_slug}/epcis/events/{dpp_id}",
    response_model=PublicEPCISQueryResponse,
)
async def get_public_epcis_events(
    tenant_slug: str,
    dpp_id: UUID,
    db: DbSession,
) -> PublicEPCISQueryResponse:
    """Get EPCIS events for a published DPP (no authentication required).

    Only returns events for DPPs with status=PUBLISHED.
    Returns the most recent 100 events while preserving chronological order.
    Ties on ``event_time`` are broken deterministically by descending row id.
    """
    tenant = await _resolve_tenant(db, tenant_slug)

    # Verify the DPP exists and is published
    result = await db.execute(
        select(DPP).where(
            DPP.id == dpp_id,
            DPP.tenant_id == tenant.id,
            DPP.status == DPPStatus.PUBLISHED,
        )
    )
    dpp = result.scalar_one_or_none()
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    # Fetch the most recent window first, then return chronologically.
    events_result = await db.execute(
        select(EPCISEvent)
        .where(
            EPCISEvent.dpp_id == dpp_id,
            EPCISEvent.tenant_id == tenant.id,
        )
        .order_by(EPCISEvent.event_time.desc(), EPCISEvent.id.desc())
        .limit(MAX_PUBLIC_EVENTS)
    )
    rows = list(reversed(events_result.scalars().all()))

    return PublicEPCISQueryResponse(
        event_list=[PublicEPCISEventResponse.model_validate(row) for row in rows],
    )
