"""
Tenant context resolution and authorization helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security.oidc import CurrentUser, TokenPayload
from app.db.models import Tenant, TenantMember, TenantRole, TenantStatus
from app.db.session import DbSession


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant context for the current request."""

    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    user: TokenPayload
    roles: tuple[str, ...]
    member_role: TenantRole | None

    @property
    def is_platform_admin(self) -> bool:
        return self.user.is_admin

    @property
    def is_tenant_admin(self) -> bool:
        return self.is_platform_admin or "tenant_admin" in self.roles

    @property
    def is_publisher(self) -> bool:
        return self.is_platform_admin or "publisher" in self.roles or self.is_tenant_admin

    @property
    def is_viewer(self) -> bool:
        return self.is_platform_admin or "viewer" in self.roles or self.is_publisher


def _expand_roles(role: TenantRole | None) -> set[str]:
    if role is None:
        return set()
    if role == TenantRole.TENANT_ADMIN:
        return {"tenant_admin", "publisher", "viewer"}
    if role == TenantRole.PUBLISHER:
        return {"publisher", "viewer"}
    return {"viewer"}


async def resolve_tenant_context(
    tenant_slug: Annotated[str, Path(..., min_length=1)],
    db: DbSession,
    user: CurrentUser,
) -> TenantContext:
    """Resolve tenant context from path and membership."""
    normalized_slug = tenant_slug.strip().lower()
    result = await db.execute(select(Tenant).where(Tenant.slug == normalized_slug))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{normalized_slug}' not found",
        )

    if tenant.status != TenantStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is inactive",
        )

    await db.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant.id)},
    )

    settings = get_settings()
    if user.is_admin and settings.db_admin_role:
        role = settings.db_admin_role.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", role):
            await db.execute(text(f'SET LOCAL ROLE "{role}"'))

    member_role: TenantRole | None = None
    roles: set[str] = set()

    if user.is_admin:
        roles = _expand_roles(TenantRole.TENANT_ADMIN)
    else:
        membership_result = await db.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id,
                TenantMember.user_subject == user.sub,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this tenant",
            )
        member_role = membership.role
        roles = _expand_roles(member_role)

    return TenantContext(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        user=user,
        roles=tuple(sorted(roles)),
        member_role=member_role,
    )


TenantContextDep = Annotated[TenantContext, Depends(resolve_tenant_context)]


async def require_tenant_member(context: TenantContextDep) -> TenantContext:
    """Require any tenant membership."""
    return context


async def require_tenant_publisher(context: TenantContextDep) -> TenantContext:
    """Require publisher or tenant admin role within the tenant."""
    if not context.is_publisher:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Publisher role required",
        )
    return context


async def require_tenant_admin(context: TenantContextDep) -> TenantContext:
    """Require tenant admin role within the tenant."""
    if not context.is_tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin role required",
        )
    return context


TenantMemberDep = Annotated[TenantContext, Depends(require_tenant_member)]
TenantPublisher = Annotated[TenantContext, Depends(require_tenant_publisher)]
TenantAdmin = Annotated[TenantContext, Depends(require_tenant_admin)]
