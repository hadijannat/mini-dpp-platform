"""Tenant management service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant, TenantMember, TenantRole, TenantStatus


class TenantService:
    """Service for tenant CRUD and membership operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tenants(self) -> list[Tenant]:
        result = await self._session.execute(select(Tenant).order_by(Tenant.created_at.desc()))
        return list(result.scalars().all())

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def create_tenant(self, slug: str, name: str) -> Tenant:
        tenant = Tenant(
            slug=slug,
            name=name,
            status=TenantStatus.ACTIVE,
        )
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    async def update_tenant(
        self,
        tenant: Tenant,
        updates: dict[str, Any],
    ) -> Tenant:
        if "name" in updates and updates["name"] is not None:
            tenant.name = str(updates["name"]).strip()
        if "status" in updates and updates["status"] is not None:
            tenant.status = updates["status"]
        await self._session.flush()
        return tenant

    async def list_members(self, tenant_id: UUID) -> list[TenantMember]:
        result = await self._session.execute(
            select(TenantMember)
            .where(TenantMember.tenant_id == tenant_id)
            .order_by(TenantMember.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_member(self, tenant_id: UUID, user_subject: str) -> TenantMember | None:
        result = await self._session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_subject == user_subject,
            )
        )
        return result.scalar_one_or_none()

    async def add_member(
        self,
        tenant_id: UUID,
        user_subject: str,
        role: TenantRole,
    ) -> TenantMember:
        member = TenantMember(
            tenant_id=tenant_id,
            user_subject=user_subject,
            role=role,
        )
        self._session.add(member)
        await self._session.flush()
        return member

    async def remove_member(self, tenant_id: UUID, user_subject: str) -> None:
        result = await self._session.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.user_subject == user_subject,
            )
        )
        member = result.scalar_one_or_none()
        if member:
            await self._session.delete(member)

    async def list_user_tenants(self, user_subject: str) -> list[tuple[Tenant, TenantMember]]:
        result = await self._session.execute(
            select(Tenant, TenantMember)
            .join(TenantMember, TenantMember.tenant_id == Tenant.id)
            .where(TenantMember.user_subject == user_subject)
            .order_by(Tenant.name.asc())
        )
        rows = result.all()
        return [(row[0], row[1]) for row in rows]
