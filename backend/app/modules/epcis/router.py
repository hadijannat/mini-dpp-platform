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
    NamedQueryCreate,
    NamedQueryResponse,
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
    try:
        result = await service.capture(
            tenant_id=tenant.tenant_id,
            dpp_id=dpp_id,
            document=document,
            created_by=tenant.user.sub,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

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
    eq_action: str | None = Query(None, alias="EQ_action"),
    eq_biz_step: str | None = Query(None, alias="EQ_bizStep"),
    eq_disposition: str | None = Query(None, alias="EQ_disposition"),
    match_epc: str | None = Query(None, alias="MATCH_epc"),
    match_any_epc: str | None = Query(None, alias="MATCH_anyEPC"),
    match_parent_id: str | None = Query(None, alias="MATCH_parentID"),
    match_input_epc: str | None = Query(None, alias="MATCH_inputEPC"),
    match_output_epc: str | None = Query(None, alias="MATCH_outputEPC"),
    eq_read_point: str | None = Query(None, alias="EQ_readPoint"),
    eq_biz_location: str | None = Query(None, alias="EQ_bizLocation"),
    ge_record_time: datetime | None = Query(None, alias="GE_recordTime"),
    lt_record_time: datetime | None = Query(None, alias="LT_recordTime"),
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
        eq_action=eq_action,
        eq_biz_step=eq_biz_step,
        eq_disposition=eq_disposition,
        match_epc=match_epc,
        match_any_epc=match_any_epc,
        match_parent_id=match_parent_id,
        match_input_epc=match_input_epc,
        match_output_epc=match_output_epc,
        eq_read_point=eq_read_point,
        eq_biz_location=eq_biz_location,
        ge_record_time=ge_record_time,
        lt_record_time=lt_record_time,
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


# ---------------------------------------------------------------------------
# Named queries
# ---------------------------------------------------------------------------


@router.post(
    "/queries",
    response_model=NamedQueryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_named_query(
    body: NamedQueryCreate,
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> NamedQueryResponse:
    """Create a saved EPCIS named query."""
    service = EPCISService(db)
    # Check for duplicate name
    existing = await service.get_named_query(tenant.tenant_id, body.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Named query '{body.name}' already exists",
        )
    return await service.create_named_query(
        tenant_id=tenant.tenant_id,
        data=body,
        created_by=tenant.user.sub,
    )


@router.get(
    "/queries",
    response_model=list[NamedQueryResponse],
)
async def list_named_queries(
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> list[NamedQueryResponse]:
    """List all named queries for the current tenant."""
    service = EPCISService(db)
    return await service.list_named_queries(tenant.tenant_id)


@router.get(
    "/queries/{name}/events",
    response_model=EPCISQueryResponse,
)
async def execute_named_query(
    name: str,
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> EPCISQueryResponse:
    """Execute a named query and return matching events."""
    service = EPCISService(db)
    try:
        events = await service.execute_named_query(tenant.tenant_id, name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Named query '{name}' not found",
        )
    return EPCISQueryResponse(event_list=events)


@router.delete(
    "/queries/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_named_query(
    name: str,
    *,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Delete a named query by name."""
    service = EPCISService(db)
    deleted = await service.delete_named_query(tenant.tenant_id, name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Named query '{name}' not found",
        )
