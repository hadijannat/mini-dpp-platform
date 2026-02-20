"""Admin audit trail endpoints for event listing, verification, and anchoring."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from app.core.config import get_settings
from app.core.crypto.hash_chain import GENESIS_HASH
from app.core.crypto.verification import verify_event, verify_hash_chain
from app.core.logging import get_logger
from app.core.security.oidc import Admin
from app.db.models import AuditEvent
from app.db.session import DbSession
from app.modules.audit.anchoring_service import AuditAnchoringService
from app.modules.audit.schemas import (
    AnchorResponse,
    AuditEventListResponse,
    AuditEventResponse,
    ChainVerificationResponse,
    EventVerificationResponse,
)

logger = get_logger(__name__)
router = APIRouter()


def _has_hash_columns() -> bool:
    """Check whether the AuditEvent model has crypto hash chain columns."""
    mapper = AuditEvent.__table__
    return all(col in mapper.columns for col in ("event_hash", "prev_event_hash", "chain_sequence"))


def _get_crypto_attr(event: AuditEvent, name: str) -> Any:
    """Safely get a crypto column attribute that may not exist on the model."""
    return getattr(event, name, None)


def _event_to_dict(event: AuditEvent) -> dict[str, object]:
    """Convert an AuditEvent ORM instance to a plain dict for verification."""
    d: dict[str, object] = {
        "action": event.action,
        "resource_type": event.resource_type,
    }
    if event.resource_id is not None:
        d["resource_id"] = event.resource_id
    if event.tenant_id is not None:
        d["tenant_id"] = str(event.tenant_id)
    if event.subject is not None:
        d["subject"] = event.subject
    if event.decision is not None:
        d["decision"] = event.decision
    if event.ip_address is not None:
        d["ip_address"] = event.ip_address
    if event.user_agent is not None:
        d["user_agent"] = event.user_agent
    if event.metadata_ is not None:
        d["metadata"] = event.metadata_

    if _has_hash_columns():
        d["event_hash"] = _get_crypto_attr(event, "event_hash")
        d["prev_event_hash"] = _get_crypto_attr(event, "prev_event_hash")
        d["chain_sequence"] = _get_crypto_attr(event, "chain_sequence")
        d["hash_algorithm"] = _get_crypto_attr(event, "hash_algorithm")
        d["hash_canonicalization"] = _get_crypto_attr(event, "hash_canonicalization")

    return d


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    db: DbSession,
    _user: Admin,
    tenant_id: UUID | None = Query(None, description="Filter by tenant"),
    action: str | None = Query(None, description="Filter by action"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> AuditEventListResponse:
    """List audit events with optional filters (admin only)."""
    query = select(AuditEvent)
    count_query = select(func.count()).select_from(AuditEvent)

    if tenant_id is not None:
        query = query.where(AuditEvent.tenant_id == tenant_id)
        count_query = count_query.where(AuditEvent.tenant_id == tenant_id)
    if action is not None:
        query = query.where(AuditEvent.action == action)
        count_query = count_query.where(AuditEvent.action == action)
    if resource_type is not None:
        query = query.where(AuditEvent.resource_type == resource_type)
        count_query = count_query.where(AuditEvent.resource_type == resource_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = (
        query.order_by(desc(AuditEvent.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    items = []
    for e in events:
        item = AuditEventResponse(
            id=e.id,
            tenant_id=e.tenant_id,
            subject=e.subject,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            decision=e.decision,
            ip_address=e.ip_address,
            user_agent=e.user_agent,
            metadata_=e.metadata_,
            created_at=e.created_at,
            event_hash=_get_crypto_attr(e, "event_hash"),
            prev_event_hash=_get_crypto_attr(e, "prev_event_hash"),
            chain_sequence=_get_crypto_attr(e, "chain_sequence"),
            hash_algorithm=_get_crypto_attr(e, "hash_algorithm"),
            hash_canonicalization=_get_crypto_attr(e, "hash_canonicalization"),
        )
        items.append(item)

    return AuditEventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/verify/chain", response_model=ChainVerificationResponse)
async def verify_chain(
    db: DbSession,
    _user: Admin,
    tenant_id: UUID = Query(..., description="Tenant ID to verify"),
) -> ChainVerificationResponse:
    """Verify the hash chain integrity for a tenant (admin only)."""
    if not _has_hash_columns():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=("Hash chain columns not available. Apply the migration first."),
        )

    query = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .where(AuditEvent.chain_sequence.is_not(None))
        .order_by(AuditEvent.chain_sequence)
    )
    result = await db.execute(query)
    events = result.scalars().all()

    event_dicts = [_event_to_dict(e) for e in events]
    chain_result = verify_hash_chain(event_dicts)

    return ChainVerificationResponse(
        is_valid=chain_result.is_valid,
        verified_count=chain_result.verified_count,
        first_break_at=chain_result.first_break_at,
        errors=chain_result.errors,
        tenant_id=tenant_id,
    )


@router.get(
    "/verify/event/{event_id}",
    response_model=EventVerificationResponse,
)
async def verify_single_event(
    db: DbSession,
    _user: Admin,
    event_id: UUID,
) -> EventVerificationResponse:
    """Verify a single audit event's hash (admin only)."""
    if not _has_hash_columns():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=("Hash chain columns not available. Apply the migration first."),
        )

    event = await db.get(AuditEvent, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit event not found",
        )

    stored_hash = _get_crypto_attr(event, "event_hash")
    if stored_hash is None:
        return EventVerificationResponse(
            is_valid=False,
            event_id=event_id,
            event_hash=None,
        )

    # Get the previous event hash
    prev_hash_stored = _get_crypto_attr(event, "prev_event_hash")
    prev_hash = prev_hash_stored if prev_hash_stored else GENESIS_HASH

    event_dict = _event_to_dict(event)
    is_valid = verify_event(event_dict, prev_hash)

    return EventVerificationResponse(
        is_valid=is_valid,
        event_id=event_id,
        event_hash=stored_hash,
    )


@router.post("/anchor", response_model=AnchorResponse)
async def anchor_merkle_root(
    db: DbSession,
    _user: Admin,
    tenant_id: UUID = Query(..., description="Tenant ID to anchor"),
) -> AnchorResponse:
    """Anchor the next unanchored audit batch (admin only)."""
    if not _has_hash_columns():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=("Hash chain columns not available. Apply the migration first."),
        )

    settings = get_settings()
    if not settings.audit_signing_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUDIT_SIGNING_KEY is not configured",
        )

    service = AuditAnchoringService(db, settings=settings)
    try:
        anchor = await service.anchor_next_batch(tenant_id=tenant_id)
    except Exception as exc:
        logger.warning(
            "audit_anchor_failed", tenant_id=str(tenant_id), error=str(exc), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to anchor audit batch: {exc}",
        ) from exc
    if anchor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No unanchored hashed audit events found for this tenant",
        )

    return AnchorResponse(
        anchor_id=anchor.id,
        merkle_root=anchor.root_hash,
        event_count=anchor.event_count,
        first_sequence=anchor.first_sequence,
        last_sequence=anchor.last_sequence,
        signature=anchor.signature,
        signature_kid=anchor.signature_kid,
        tsa_token_present=anchor.tsa_token is not None,
        tenant_id=tenant_id,
    )
