"""Tenant management API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import Admin, CurrentUser
from app.core.tenancy import TenantAdmin, TenantContextDep
from app.db.models import TenantRole, TenantStatus
from app.db.session import DbSession
from app.modules.tenants.service import TenantService

router = APIRouter()


class TenantCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=255)


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    status: TenantStatus | None = None


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    status: str
    created_at: str
    updated_at: str


class TenantListResponse(BaseModel):
    tenants: list[TenantResponse]
    count: int


class TenantMembershipResponse(BaseModel):
    slug: str
    name: str
    status: str
    role: str


class TenantMembershipListResponse(BaseModel):
    tenants: list[TenantMembershipResponse]
    count: int


class TenantMemberRequest(BaseModel):
    user_subject: str = Field(..., min_length=1, max_length=255)
    role: TenantRole = TenantRole.VIEWER


class TenantMemberResponse(BaseModel):
    user_subject: str
    role: str
    created_at: str


class TenantMemberListResponse(BaseModel):
    members: list[TenantMemberResponse]
    count: int


@router.get("/mine", response_model=TenantMembershipListResponse)
async def list_my_tenants(
    db: DbSession,
    user: CurrentUser,
) -> TenantMembershipListResponse:
    """List tenants the current user belongs to."""
    service = TenantService(db)
    memberships = await service.list_user_tenants(user.sub)

    return TenantMembershipListResponse(
        tenants=[
            TenantMembershipResponse(
                slug=tenant.slug,
                name=tenant.name,
                status=tenant.status.value,
                role=member.role.value,
            )
            for tenant, member in memberships
        ],
        count=len(memberships),
    )


@router.get("", response_model=TenantListResponse)
async def list_tenants(db: DbSession, _user: Admin) -> TenantListResponse:
    """List all tenants (platform admin)."""
    service = TenantService(db)
    tenants = await service.list_tenants()

    return TenantListResponse(
        tenants=[
            TenantResponse(
                id=tenant.id,
                slug=tenant.slug,
                name=tenant.name,
                status=tenant.status.value,
                created_at=tenant.created_at.isoformat(),
                updated_at=tenant.updated_at.isoformat(),
            )
            for tenant in tenants
        ],
        count=len(tenants),
    )


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    db: DbSession,
    _user: Admin,
) -> TenantResponse:
    """Create a new tenant (platform admin)."""
    service = TenantService(db)
    slug = request.slug.strip().lower()
    name = request.name.strip()

    existing = await service.get_tenant_by_slug(slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant slug already exists",
        )

    tenant = await service.create_tenant(slug=slug, name=name)
    await db.commit()
    await db.refresh(tenant)

    return TenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        status=tenant.status.value,
        created_at=tenant.created_at.isoformat(),
        updated_at=tenant.updated_at.isoformat(),
    )


@router.get("/{tenant_slug}", response_model=TenantResponse)
async def get_tenant(
    db: DbSession,
    tenant: TenantContextDep,
) -> TenantResponse:
    """Get tenant details (tenant member)."""
    service = TenantService(db)
    record = await service.get_tenant_by_slug(tenant.tenant_slug)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant.tenant_slug}' not found",
        )

    return TenantResponse(
        id=record.id,
        slug=record.slug,
        name=record.name,
        status=record.status.value,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.patch("/{tenant_slug}", response_model=TenantResponse)
async def update_tenant(
    request: TenantUpdateRequest,
    db: DbSession,
    _user: Admin,
    tenant_slug: str,
) -> TenantResponse:
    """Update tenant metadata (platform admin)."""
    service = TenantService(db)
    normalized_slug = tenant_slug.strip().lower()
    tenant = await service.get_tenant_by_slug(normalized_slug)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{normalized_slug}' not found",
        )

    updated = await service.update_tenant(
        tenant,
        {"name": request.name, "status": request.status},
    )
    await db.commit()

    return TenantResponse(
        id=updated.id,
        slug=updated.slug,
        name=updated.name,
        status=updated.status.value,
        created_at=updated.created_at.isoformat(),
        updated_at=updated.updated_at.isoformat(),
    )


@router.get("/{tenant_slug}/members", response_model=TenantMemberListResponse)
async def list_members(
    db: DbSession,
    tenant: TenantAdmin,
) -> TenantMemberListResponse:
    """List members of a tenant (tenant admin)."""
    service = TenantService(db)
    members = await service.list_members(tenant.tenant_id)

    return TenantMemberListResponse(
        members=[
            TenantMemberResponse(
                user_subject=member.user_subject,
                role=member.role.value,
                created_at=member.created_at.isoformat(),
            )
            for member in members
        ],
        count=len(members),
    )


@router.post("/{tenant_slug}/members", response_model=TenantMemberResponse)
async def add_member(
    request: TenantMemberRequest,
    db: DbSession,
    tenant: TenantAdmin,
) -> TenantMemberResponse:
    """Add a member to a tenant (tenant admin)."""
    if request.role == TenantRole.TENANT_ADMIN and not tenant.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admins can grant tenant_admin",
        )

    service = TenantService(db)
    existing = await service.get_member(tenant.tenant_id, request.user_subject)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already exists for this tenant",
        )
    member = await service.add_member(
        tenant_id=tenant.tenant_id,
        user_subject=request.user_subject,
        role=request.role,
    )
    await db.commit()

    return TenantMemberResponse(
        user_subject=member.user_subject,
        role=member.role.value,
        created_at=member.created_at.isoformat(),
    )


@router.delete("/{tenant_slug}/members/{user_subject}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_subject: str,
    db: DbSession,
    tenant: TenantAdmin,
) -> None:
    """Remove a member from a tenant (tenant admin)."""
    service = TenantService(db)
    await service.remove_member(tenant.tenant_id, user_subject)
    await db.commit()
