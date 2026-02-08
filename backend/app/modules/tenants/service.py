"""Tenant management service."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DPP,
    AuditEvent,
    DPPRevision,
    DPPStatus,
    EPCISEvent,
    Tenant,
    TenantMember,
    TenantRole,
    TenantStatus,
)


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

    async def update_member_role(
        self,
        tenant_id: UUID,
        user_subject: str,
        role: TenantRole,
    ) -> TenantMember | None:
        member = await self.get_member(tenant_id, user_subject)
        if member is None:
            return None
        member.role = role
        await self._session.flush()
        return member

    async def get_platform_metrics(self) -> list[dict[str, Any]]:
        """Get per-tenant usage metrics using a single aggregated query."""
        draft_val = DPPStatus.DRAFT.value
        published_val = DPPStatus.PUBLISHED.value
        archived_val = DPPStatus.ARCHIVED.value

        query = (
            select(
                Tenant.id.label("tenant_id"),
                Tenant.slug.label("slug"),
                Tenant.name.label("name"),
                Tenant.status.label("status"),
                func.coalesce(
                    select(func.count(DPP.id))
                    .where(DPP.tenant_id == Tenant.id)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("total_dpps"),
                func.coalesce(
                    select(func.count(DPP.id))
                    .where(DPP.tenant_id == Tenant.id, DPP.status == draft_val)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("draft_dpps"),
                func.coalesce(
                    select(func.count(DPP.id))
                    .where(DPP.tenant_id == Tenant.id, DPP.status == published_val)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("published_dpps"),
                func.coalesce(
                    select(func.count(DPP.id))
                    .where(DPP.tenant_id == Tenant.id, DPP.status == archived_val)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("archived_dpps"),
                func.coalesce(
                    select(func.count(DPPRevision.id))
                    .where(DPPRevision.tenant_id == Tenant.id)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("total_revisions"),
                func.coalesce(
                    select(func.count(TenantMember.id))
                    .where(TenantMember.tenant_id == Tenant.id)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("total_members"),
                func.coalesce(
                    select(func.count(EPCISEvent.id))
                    .where(EPCISEvent.tenant_id == Tenant.id)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("total_epcis_events"),
                func.coalesce(
                    select(func.count(AuditEvent.id))
                    .where(AuditEvent.tenant_id == Tenant.id)
                    .correlate(Tenant)
                    .scalar_subquery(),
                    0,
                ).label("total_audit_events"),
            )
            .order_by(Tenant.name.asc())
        )

        result = await self._session.execute(query)
        rows = result.all()
        return [
            {
                "tenant_id": str(row.tenant_id),
                "slug": row.slug,
                "name": row.name,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "total_dpps": row.total_dpps,
                "draft_dpps": row.draft_dpps,
                "published_dpps": row.published_dpps,
                "archived_dpps": row.archived_dpps,
                "total_revisions": row.total_revisions,
                "total_members": row.total_members,
                "total_epcis_events": row.total_epcis_events,
                "total_audit_events": row.total_audit_events,
            }
            for row in rows
        ]

    async def list_user_tenants(self, user_subject: str) -> list[tuple[Tenant, TenantMember]]:
        result = await self._session.execute(
            select(Tenant, TenantMember)
            .join(TenantMember, TenantMember.tenant_id == Tenant.id)
            .where(TenantMember.user_subject == user_subject)
            .order_by(Tenant.name.asc())
        )
        rows = result.all()
        return [(row[0], row[1]) for row in rows]
