"""Tenant-scoped RFID APIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.security import require_access
from app.core.tenancy import TenantPublisher
from app.db.session import DbSession
from app.modules.rfid.schemas import (
    RFIDDecodeRequest,
    RFIDDecodeResponse,
    RFIDEncodeRequest,
    RFIDEncodeResponse,
    RFIDReadsIngestRequest,
    RFIDReadsIngestResponse,
)
from app.modules.rfid.service import RFIDError, RFIDService, RFIDSidecarUnavailableError

router = APIRouter()


@router.post("/encode", response_model=RFIDEncodeResponse)
async def encode_rfid_tag(
    body: RFIDEncodeRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> RFIDEncodeResponse:
    await require_access(
        tenant.user,
        "create",
        {"type": "data_carrier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = RFIDService(db)
    try:
        return await service.encode(tenant_id=tenant.tenant_id, request=body)
    except RFIDSidecarUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RFIDError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/decode", response_model=RFIDDecodeResponse)
async def decode_rfid_tag(
    body: RFIDDecodeRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> RFIDDecodeResponse:
    await require_access(
        tenant.user,
        "read",
        {"type": "data_carrier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = RFIDService(db)
    try:
        return await service.decode(body)
    except RFIDSidecarUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RFIDError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/reads", response_model=RFIDReadsIngestResponse)
async def ingest_rfid_reads(
    body: RFIDReadsIngestRequest,
    db: DbSession,
    tenant: TenantPublisher,
) -> RFIDReadsIngestResponse:
    await require_access(
        tenant.user,
        "update",
        {"type": "data_carrier", "owner_subject": tenant.user.sub},
        tenant=tenant,
    )
    service = RFIDService(db)
    try:
        response = await service.ingest_reads(
            tenant_id=tenant.tenant_id,
            created_by=tenant.user.sub,
            request=body,
        )
    except RFIDSidecarUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RFIDError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    await db.commit()
    return response
