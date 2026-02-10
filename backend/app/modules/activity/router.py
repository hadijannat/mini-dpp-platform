"""Tenant-scoped activity and resource timeline endpoints."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from app.core.security import require_access
from app.core.security.actor_metadata import actor_payload, load_users_by_subject
from app.core.security.resource_context import (
    build_connector_resource_context,
    build_dpp_resource_context,
)
from app.core.tenancy import TenantPublisher
from app.db.models import AuditEvent
from app.db.session import DbSession
from app.modules.connectors.catenax.service import CatenaXConnectorService
from app.modules.dpps.service import DPPService

router = APIRouter()

ResourceType = Literal["dpp", "connector"]


class ActorSummary(BaseModel):
    """Actor metadata for activity responses."""

    subject: str
    display_name: str | None = None
    email_masked: str | None = None


class ActivityEventResponse(BaseModel):
    """Single activity event row."""

    id: UUID
    subject: str | None = None
    actor: ActorSummary | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    decision: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str


class ActivityEventListResponse(BaseModel):
    """Paginated activity event list."""

    events: list[ActivityEventResponse]
    count: int
    total_count: int
    limit: int
    offset: int


async def _ensure_resource_read_access(
    *,
    db: DbSession,
    tenant: TenantPublisher,
    resource_type: ResourceType,
    resource_id: UUID,
) -> None:
    if resource_type == "dpp":
        dpp_service = DPPService(db)
        dpp = await dpp_service.get_dpp(resource_id, tenant.tenant_id)
        if not dpp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DPP {resource_id} not found",
            )
        shared = await dpp_service.is_resource_shared_with_user(
            tenant_id=tenant.tenant_id,
            resource_type="dpp",
            resource_id=dpp.id,
            user_subject=tenant.user.sub,
        )
        await require_access(
            tenant.user,
            "read",
            build_dpp_resource_context(dpp, shared_with_current_user=shared),
            tenant=tenant,
        )
        return

    connector_service = CatenaXConnectorService(db)
    connector = await connector_service.get_connector(resource_id, tenant.tenant_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {resource_id} not found",
        )
    shared = await connector_service.is_connector_shared_with_user(
        tenant_id=tenant.tenant_id,
        connector_id=connector.id,
        user_subject=tenant.user.sub,
    )
    await require_access(
        tenant.user,
        "read",
        build_connector_resource_context(connector, shared_with_current_user=shared),
        tenant=tenant,
    )


def _event_payload(event: AuditEvent, users_by_subject: dict[str, Any]) -> ActivityEventResponse:
    actor = None
    if event.subject:
        actor = ActorSummary(**actor_payload(event.subject, users_by_subject))
    return ActivityEventResponse(
        id=event.id,
        subject=event.subject,
        actor=actor,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        decision=event.decision,
        metadata=event.metadata_,
        created_at=event.created_at.isoformat(),
    )


@router.get("/events", response_model=ActivityEventListResponse)
async def list_activity_events(
    db: DbSession,
    tenant: TenantPublisher,
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ActivityEventListResponse:
    """List activity events scoped to tenant and caller privileges."""
    query = select(AuditEvent).where(AuditEvent.tenant_id == tenant.tenant_id)
    if resource_type:
        query = query.where(AuditEvent.resource_type == resource_type)
    if action:
        query = query.where(AuditEvent.action == action)

    if not tenant.is_tenant_admin:
        query = query.where(AuditEvent.subject == tenant.user.sub)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total_count = int(total_result.scalar_one())

    result = await db.execute(
        query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    )
    events = list(result.scalars().all())
    users = await load_users_by_subject(
        db,
        [event.subject for event in events if event.subject],
    )

    payload = [_event_payload(event, users) for event in events]
    return ActivityEventListResponse(
        events=payload,
        count=len(payload),
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/resources/{resource_type}/{resource_id}", response_model=ActivityEventListResponse)
async def get_resource_activity(
    resource_type: ResourceType,
    resource_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
) -> ActivityEventListResponse:
    """Get timeline events for a specific resource."""
    await _ensure_resource_read_access(
        db=db,
        tenant=tenant,
        resource_type=resource_type,
        resource_id=resource_id,
    )

    resource_id_str = str(resource_id)
    base_query = select(AuditEvent).where(
        AuditEvent.tenant_id == tenant.tenant_id,
        AuditEvent.resource_type == resource_type,
        AuditEvent.resource_id == resource_id_str,
    )

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total_count = int(total_result.scalar_one())

    result = await db.execute(
        base_query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    )
    events = list(result.scalars().all())
    users = await load_users_by_subject(
        db,
        [event.subject for event in events if event.subject],
    )
    payload = [_event_payload(event, users) for event in events]

    return ActivityEventListResponse(
        events=payload,
        count=len(payload),
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
