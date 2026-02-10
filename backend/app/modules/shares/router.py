"""Resource sharing endpoints for owner/team scoped resources."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.audit import emit_audit_event
from app.core.security.actor_metadata import actor_payload, load_users_by_subject
from app.core.tenancy import TenantPublisher
from app.db.models import DPP, Connector, ResourceShare
from app.db.session import DbSession

router = APIRouter()

ResourceType = Literal["dpp", "connector"]


class ActorSummary(BaseModel):
    """Actor identity summary for share responses."""

    subject: str
    display_name: str | None = None
    email_masked: str | None = None


class ResourceShareRequest(BaseModel):
    """Request payload for grant/update share."""

    user_subject: str
    permission: str = "read"
    expires_at: datetime | None = None


class ResourceShareResponse(BaseModel):
    """Single share record."""

    id: UUID
    resource_type: ResourceType
    resource_id: UUID
    user_subject: str
    user: ActorSummary
    permission: str
    granted_by_subject: str
    granted_by: ActorSummary
    created_at: str
    expires_at: str | None = None


class ResourceShareListResponse(BaseModel):
    """Share list response."""

    shares: list[ResourceShareResponse]
    count: int


async def _load_resource_owner_subject(
    *,
    db: DbSession,
    tenant_id: UUID,
    resource_type: ResourceType,
    resource_id: UUID,
) -> str:
    if resource_type == "dpp":
        result = await db.execute(
            select(DPP.owner_subject).where(
                DPP.id == resource_id,
                DPP.tenant_id == tenant_id,
            )
        )
    else:
        result = await db.execute(
            select(Connector.created_by_subject).where(
                Connector.id == resource_id,
                Connector.tenant_id == tenant_id,
            )
        )
    owner_subject = result.scalar_one_or_none()
    if owner_subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type} {resource_id} not found",
        )
    return str(owner_subject)


def _share_payload(
    share: ResourceShare,
    users_by_subject: dict[str, Any],
) -> ResourceShareResponse:
    return ResourceShareResponse(
        id=share.id,
        resource_type=share.resource_type,
        resource_id=share.resource_id,
        user_subject=share.user_subject,
        user=ActorSummary(**actor_payload(share.user_subject, users_by_subject)),
        permission=share.permission,
        granted_by_subject=share.granted_by_subject,
        granted_by=ActorSummary(**actor_payload(share.granted_by_subject, users_by_subject)),
        created_at=share.created_at.isoformat(),
        expires_at=share.expires_at.isoformat() if share.expires_at else None,
    )


def _can_manage_shares(*, tenant: TenantPublisher, owner_subject: str) -> bool:
    return tenant.is_tenant_admin or tenant.user.sub == owner_subject


@router.get("/{resource_type}/{resource_id}", response_model=ResourceShareListResponse)
async def list_resource_shares(
    resource_type: ResourceType,
    resource_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> ResourceShareListResponse:
    """List active shares for a resource."""
    owner_subject = await _load_resource_owner_subject(
        db=db,
        tenant_id=tenant.tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if not _can_manage_shares(tenant=tenant, owner_subject=owner_subject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only resource owner or tenant admin can view shares",
        )

    result = await db.execute(
        select(ResourceShare).where(
            ResourceShare.tenant_id == tenant.tenant_id,
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
        )
    )
    shares = list(result.scalars().all())
    users = await load_users_by_subject(
        db,
        [*{s.user_subject for s in shares}, *{s.granted_by_subject for s in shares}],
    )
    return ResourceShareListResponse(
        shares=[_share_payload(share, users) for share in shares],
        count=len(shares),
    )


@router.post("/{resource_type}/{resource_id}", response_model=ResourceShareResponse)
async def grant_resource_share(
    resource_type: ResourceType,
    resource_id: UUID,
    body: ResourceShareRequest,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> ResourceShareResponse:
    """Grant or update explicit share access for a resource."""
    owner_subject = await _load_resource_owner_subject(
        db=db,
        tenant_id=tenant.tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if not _can_manage_shares(tenant=tenant, owner_subject=owner_subject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only resource owner or tenant admin can manage shares",
        )

    existing_result = await db.execute(
        select(ResourceShare).where(
            ResourceShare.tenant_id == tenant.tenant_id,
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
            ResourceShare.user_subject == body.user_subject,
        )
    )
    share = existing_result.scalar_one_or_none()
    if share:
        share.permission = body.permission
        share.expires_at = body.expires_at
        share.granted_by_subject = tenant.user.sub
    else:
        share = ResourceShare(
            tenant_id=tenant.tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_subject=body.user_subject,
            permission=body.permission,
            granted_by_subject=tenant.user.sub,
            expires_at=body.expires_at,
        )
        db.add(share)

    await db.flush()
    await emit_audit_event(
        db_session=db,
        action="resource_share_granted",
        resource_type=resource_type,
        resource_id=str(resource_id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={
            "shared_user_subject": body.user_subject,
            "permission": body.permission,
            "expires_at": body.expires_at.isoformat() if body.expires_at else None,
        },
    )
    await db.commit()

    users = await load_users_by_subject(db, [share.user_subject, share.granted_by_subject])
    return _share_payload(share, users)


@router.delete(
    "/{resource_type}/{resource_id}/{user_subject}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_resource_share(
    resource_type: ResourceType,
    resource_id: UUID,
    user_subject: str,
    request: Request,
    db: DbSession,
    tenant: TenantPublisher,
) -> None:
    """Revoke share access for a specific subject."""
    owner_subject = await _load_resource_owner_subject(
        db=db,
        tenant_id=tenant.tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if not _can_manage_shares(tenant=tenant, owner_subject=owner_subject):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only resource owner or tenant admin can manage shares",
        )

    result = await db.execute(
        select(ResourceShare).where(
            ResourceShare.tenant_id == tenant.tenant_id,
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
            ResourceShare.user_subject == user_subject,
        )
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    await db.delete(share)
    await emit_audit_event(
        db_session=db,
        action="resource_share_revoked",
        resource_type=resource_type,
        resource_id=str(resource_id),
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
        metadata={"shared_user_subject": user_subject},
    )
    await db.commit()
