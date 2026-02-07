"""API router for EPCIS 2.0 event capture and query endpoints.

All endpoints require publisher role and tenant context. Events are
append-only — no update or delete endpoints per the EPCIS specification.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.core.audit import emit_audit_event
from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.models import DPP, EPCISEventType
from app.db.session import DbSession
from app.modules.dpps.service import DPPService

from .schemas import (
    CaptureResponse,
    EPCISDocumentCreate,
    EPCISEventResponse,
    EPCISQueryParams,
    EPCISQueryResponse,
)
from .service import EPCISService

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dpp_resource(dpp_id: UUID, owner_subject: str) -> dict[str, str]:
    """Build an ABAC resource context dict for a DPP."""
    return {"type": "dpp", "id": str(dpp_id), "owner_subject": owner_subject}


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
    await require_access(
        tenant.user,
        action,
        _dpp_resource(dpp.id, dpp.owner_subject),
        tenant=tenant,
    )
    return dpp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/capture",
    response_model=CaptureResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def capture_events(
    document: EPCISDocumentCreate,
    dpp_id: UUID = Query(..., description="DPP to link captured events to"),
    *,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> CaptureResponse:
    """Capture an EPCIS 2.0 document — persist all events for a DPP.

    Returns HTTP 202 (Accepted) per the EPCIS capture interface spec.
    """
    await _get_dpp_or_404(dpp_id, tenant, db, action="update")

    service = EPCISService(db)
    result = await service.capture(
        tenant_id=tenant.tenant_id,
        dpp_id=dpp_id,
        document=document,
        created_by=tenant.user.sub,
    )

    await emit_audit_event(
        db_session=db,
        action="epcis_capture",
        resource_type="dpp",
        resource_id=dpp_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"capture_id": result.capture_id, "event_count": result.event_count},
    )

    return result


@router.get(
    "/events",
    response_model=EPCISQueryResponse,
)
async def query_events(
    event_type: EPCISEventType | None = None,
    ge_event_time: datetime | None = Query(None, alias="GE_eventTime"),
    lt_event_time: datetime | None = Query(None, alias="LT_eventTime"),
    eq_biz_step: str | None = Query(None, alias="EQ_bizStep"),
    eq_disposition: str | None = Query(None, alias="EQ_disposition"),
    match_epc: str | None = Query(None, alias="MATCH_epc"),
    eq_read_point: str | None = Query(None, alias="EQ_readPoint"),
    eq_biz_location: str | None = Query(None, alias="EQ_bizLocation"),
    dpp_id: UUID | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> EPCISQueryResponse:
    """Query EPCIS events using SimpleEventQuery-style filters."""
    filters = EPCISQueryParams(
        event_type=event_type,
        ge_event_time=ge_event_time,
        lt_event_time=lt_event_time,
        eq_biz_step=eq_biz_step,
        eq_disposition=eq_disposition,
        match_epc=match_epc,
        eq_read_point=eq_read_point,
        eq_biz_location=eq_biz_location,
        dpp_id=dpp_id,
        limit=limit,
        offset=offset,
    )

    service = EPCISService(db)
    events = await service.query(tenant.tenant_id, filters)

    return EPCISQueryResponse(event_list=events)


@router.get(
    "/events/{event_id:path}",
    response_model=EPCISEventResponse,
)
async def get_event(
    event_id: str,
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> EPCISEventResponse:
    """Get a single EPCIS event by its event_id URI."""
    service = EPCISService(db)
    result = await service.get_by_id(tenant.tenant_id, event_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EPCIS event '{event_id}' not found",
        )
    return result
