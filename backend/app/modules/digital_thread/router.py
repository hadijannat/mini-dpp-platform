"""API router for digital thread event endpoints.

All endpoints require publisher role and tenant context.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.security.resource_context import build_dpp_resource_context
from app.core.tenancy import TenantPublisher
from app.db.models import DPP, LifecyclePhase
from app.db.session import DbSession
from app.modules.dpps.service import DPPService

from .projections import get_compliance_timeline, get_lifecycle_timeline
from .schemas import (
    EventQuery,
    LifecycleTimeline,
    ThreadEventCreate,
    ThreadEventResponse,
)
from .service import ThreadService

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_dpp_or_404(
    dpp_id: UUID,
    tenant: TenantPublisher,
    db: DbSession,
    *,
    action: str = "read",
) -> DPP:
    """Load a DPP and check ABAC access, raising 404/403 as needed."""
    dpp_service = DPPService(db)
    dpp = await dpp_service.get_dpp(dpp_id, tenant.tenant_id)
    if not dpp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DPP {dpp_id} not found",
        )
    shared_with_current_user = await dpp_service.is_resource_shared_with_user(
        tenant_id=tenant.tenant_id,
        resource_type="dpp",
        resource_id=dpp.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        action,
        build_dpp_resource_context(
            dpp,
            shared_with_current_user=shared_with_current_user,
        ),
        tenant=tenant,
    )
    return dpp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    response_model=ThreadEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_event(
    body: ThreadEventCreate,
    dpp_id: UUID = Query(..., description="DPP to attach the event to"),
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> ThreadEventResponse:
    """Record a new digital thread event for a DPP."""
    await _get_dpp_or_404(dpp_id, tenant, db, action="update")

    service = ThreadService(db)
    try:
        result = await service.record_event(
            dpp_id=dpp_id,
            tenant_id=tenant.tenant_id,
            event=body,
            created_by=tenant.user.sub,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await emit_audit_event(
        db_session=db,
        action="record_thread_event",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "phase": body.phase.value,
            "event_type": body.event_type,
            "source": body.source,
        },
    )

    return result


@router.get(
    "/events",
    response_model=list[ThreadEventResponse],
)
async def list_events(
    dpp_id: UUID = Query(..., description="DPP to query events for"),
    phase: str | None = Query(None, description="Filter by lifecycle phase"),
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> list[ThreadEventResponse]:
    """Query digital thread events with optional filters."""
    await _get_dpp_or_404(dpp_id, tenant, db)

    parsed_phase: LifecyclePhase | None = None
    if phase is not None:
        try:
            parsed_phase = LifecyclePhase(phase)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid lifecycle phase: {phase}",
            ) from exc

    query = EventQuery(
        dpp_id=dpp_id,
        phase=parsed_phase,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    service = ThreadService(db)
    return await service.get_events(tenant.tenant_id, query)


@router.get(
    "/timeline/{dpp_id}",
    response_model=LifecycleTimeline,
)
async def get_timeline(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> LifecycleTimeline:
    """Get full lifecycle timeline for a DPP, grouped by phase."""
    await _get_dpp_or_404(dpp_id, tenant, db)
    return await get_lifecycle_timeline(db, dpp_id, tenant.tenant_id)


@router.get(
    "/timeline/{dpp_id}/compliance",
    response_model=LifecycleTimeline,
)
async def get_compliance_timeline_endpoint(
    dpp_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> LifecycleTimeline:
    """Get compliance-relevant timeline for a DPP.

    Returns only events from MANUFACTURE, DEPLOY, and END_OF_LIFE phases
    whose event types contain compliance-related keywords.
    """
    await _get_dpp_or_404(dpp_id, tenant, db)
    return await get_compliance_timeline(db, dpp_id, tenant.tenant_id)
