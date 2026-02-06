"""
API Router for Policy management endpoints.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.audit import emit_audit_event
from app.core.tenancy import TenantAdmin, TenantPublisher
from app.db.models import DPP, Policy, PolicyEffect, PolicyType
from app.db.session import DbSession

router = APIRouter()


class PolicyCreateRequest(BaseModel):
    """Request model for creating a policy."""

    dpp_id: UUID | None = None
    policy_type: PolicyType
    target: str
    effect: PolicyEffect
    rules: dict[str, Any]
    priority: int = 0
    description: str | None = None


class PolicyResponse(BaseModel):
    """Response model for policy data."""

    id: UUID
    dpp_id: UUID | None
    policy_type: str
    target: str
    effect: str
    rules: dict[str, Any]
    priority: int
    description: str | None
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class PolicyListResponse(BaseModel):
    """Response model for list of policies."""

    policies: list[PolicyResponse]
    count: int


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    db: DbSession,
    tenant: TenantPublisher,
    dpp_id: UUID | None = Query(None, description="Filter by DPP ID"),
    policy_type: PolicyType | None = Query(None, description="Filter by policy type"),
) -> PolicyListResponse:
    """
    List all policies.

    Requires publisher role. Can filter by DPP ID or policy type.
    """
    query = (
        select(Policy)
        .where(Policy.tenant_id == tenant.tenant_id)
        .order_by(Policy.priority.desc(), Policy.created_at.desc())
    )

    if dpp_id:
        query = query.where(Policy.dpp_id == dpp_id)

    if policy_type:
        query = query.where(Policy.policy_type == policy_type)

    result = await db.execute(query)
    policies = list(result.scalars().all())

    return PolicyListResponse(
        policies=[
            PolicyResponse(
                id=p.id,
                dpp_id=p.dpp_id,
                policy_type=p.policy_type.value,
                target=p.target,
                effect=p.effect.value,
                rules=p.rules,
                priority=p.priority,
                description=p.description,
                is_active=p.is_active,
                created_at=p.created_at.isoformat(),
            )
            for p in policies
        ],
        count=len(policies),
    )


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(
    request: PolicyCreateRequest,
    db: DbSession,
    tenant: TenantAdmin,
    http_request: Request,
) -> PolicyResponse:
    """
    Create a new policy.

    Requires admin role.
    """
    if request.dpp_id:
        result = await db.execute(
            select(DPP).where(
                DPP.id == request.dpp_id,
                DPP.tenant_id == tenant.tenant_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DPP {request.dpp_id} not found",
            )

    policy = Policy(
        tenant_id=tenant.tenant_id,
        dpp_id=request.dpp_id,
        policy_type=request.policy_type,
        target=request.target,
        effect=request.effect,
        rules=request.rules,
        priority=request.priority,
        description=request.description,
    )

    db.add(policy)
    await db.flush()

    await emit_audit_event(
        db_session=db,
        action="create_policy",
        resource_type="policy",
        resource_id=policy.id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=http_request,
        metadata={"policy_type": request.policy_type.value, "effect": request.effect.value},
    )

    await db.commit()
    await db.refresh(policy)

    return PolicyResponse(
        id=policy.id,
        dpp_id=policy.dpp_id,
        policy_type=policy.policy_type.value,
        target=policy.target,
        effect=policy.effect.value,
        rules=policy.rules,
        priority=policy.priority,
        description=policy.description,
        is_active=policy.is_active,
        created_at=policy.created_at.isoformat(),
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: UUID,
    db: DbSession,
    tenant: TenantPublisher,
) -> PolicyResponse:
    """
    Get a specific policy by ID.
    """
    result = await db.execute(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.tenant_id == tenant.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )

    return PolicyResponse(
        id=policy.id,
        dpp_id=policy.dpp_id,
        policy_type=policy.policy_type.value,
        target=policy.target,
        effect=policy.effect.value,
        rules=policy.rules,
        priority=policy.priority,
        description=policy.description,
        is_active=policy.is_active,
        created_at=policy.created_at.isoformat(),
    )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: UUID,
    db: DbSession,
    tenant: TenantAdmin,
    request: Request,
) -> None:
    """
    Delete a policy.

    Requires admin role.
    """
    result = await db.execute(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.tenant_id == tenant.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()

    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy {policy_id} not found",
        )

    await emit_audit_event(
        db_session=db,
        action="delete_policy",
        resource_type="policy",
        resource_id=policy_id,
        tenant_id=tenant.tenant_id,
        user=tenant.user,
        request=request,
    )

    await db.delete(policy)
    await db.commit()
