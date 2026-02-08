"""Service layer for GS1 Digital Link resolver."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ResolverLink
from app.modules.resolver.schemas import (
    LinksetLink,
    LinkType,
    ResolverLinkCreate,
    ResolverLinkUpdate,
)

logger = get_logger(__name__)


class ResolverService:
    """CRUD and resolution logic for GS1 Digital Link resolver entries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_link(
        self,
        tenant_id: UUID,
        link_create: ResolverLinkCreate,
        created_by: str,
        dpp_id: UUID | None = None,
    ) -> ResolverLink:
        """Create a new resolver link."""
        effective_dpp_id = link_create.dpp_id or dpp_id
        link = ResolverLink(
            tenant_id=tenant_id,
            identifier=link_create.identifier,
            link_type=link_create.link_type.value,
            href=link_create.href,
            media_type=link_create.media_type,
            title=link_create.title,
            hreflang=link_create.hreflang,
            priority=link_create.priority,
            dpp_id=effective_dpp_id,
            active=True,
            created_by_subject=created_by,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def get_link(
        self,
        link_id: UUID,
        tenant_id: UUID,
    ) -> ResolverLink | None:
        """Get a single resolver link by ID."""
        result = await self._session.execute(
            select(ResolverLink).where(
                ResolverLink.id == link_id,
                ResolverLink.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_links(
        self,
        tenant_id: UUID,
        dpp_id: UUID | None = None,
        active_only: bool = True,
    ) -> list[ResolverLink]:
        """List resolver links for a tenant, optionally filtered by DPP."""
        stmt = select(ResolverLink).where(ResolverLink.tenant_id == tenant_id)
        if dpp_id is not None:
            stmt = stmt.where(ResolverLink.dpp_id == dpp_id)
        if active_only:
            stmt = stmt.where(ResolverLink.active.is_(True))
        stmt = stmt.order_by(ResolverLink.priority.desc(), ResolverLink.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_link(
        self,
        link_id: UUID,
        tenant_id: UUID,
        link_update: ResolverLinkUpdate,
    ) -> ResolverLink | None:
        """Update an existing resolver link."""
        link = await self.get_link(link_id, tenant_id)
        if not link:
            return None
        update_data = link_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(link, field, value)
        await self._session.flush()
        return link

    async def delete_link(
        self,
        link_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Delete a resolver link. Returns True if found and deleted."""
        link = await self.get_link(link_id, tenant_id)
        if not link:
            return False
        await self._session.delete(link)
        await self._session.flush()
        return True

    async def resolve(
        self,
        identifier: str,
        link_type_filter: str | None = None,
        limit: int = 100,
    ) -> list[ResolverLink]:
        """Resolve an identifier to active links across all tenants."""
        stmt = select(ResolverLink).where(
            ResolverLink.identifier == identifier,
            ResolverLink.active.is_(True),
        )
        if link_type_filter:
            stmt = stmt.where(ResolverLink.link_type == link_type_filter)
        stmt = stmt.order_by(ResolverLink.priority.desc(), ResolverLink.created_at)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def build_linkset(links: list[ResolverLink], anchor_uri: str) -> dict[str, Any]:
        """Build RFC 9264 linkset JSON from resolver links."""
        grouped: dict[str, list[LinksetLink]] = {}
        for link in links:
            entry = LinksetLink(
                href=link.href,
                type=link.media_type or None,
                title=link.title or None,
                hreflang=link.hreflang or None,
            )
            grouped.setdefault(link.link_type, []).append(entry)

        return {
            "linkset": [
                {
                    "anchor": anchor_uri,
                    **{
                        rel: [e.model_dump(exclude_none=True) for e in entries]
                        for rel, entries in grouped.items()
                    },
                }
            ]
        }

    async def auto_register_for_dpp(
        self,
        dpp: Any,
        tenant_id: UUID,
        created_by: str,
        base_url: str,
    ) -> None:
        """Create default resolver links for a published DPP.

        Extracts GTIN/serial from ``dpp.asset_ids`` and creates a
        ``gs1:hasDigitalProductPassport`` link pointing to the public
        DPP endpoint. Skips if a link already exists for the identifier
        and link type.
        """
        from app.modules.qr.service import QRCodeService

        qr_service = QRCodeService()
        gtin, serial, _is_pseudo = qr_service.extract_gtin_from_asset_ids(dpp.asset_ids)

        if not gtin or not serial:
            logger.warning(
                "resolver_auto_register_skip_no_ids",
                dpp_id=str(dpp.id),
            )
            return

        identifier = f"01/{gtin}/21/{serial}"
        link_type = LinkType.HAS_DPP.value

        # Check for existing link
        existing = await self._session.execute(
            select(ResolverLink).where(
                ResolverLink.tenant_id == tenant_id,
                ResolverLink.identifier == identifier,
                ResolverLink.link_type == link_type,
            )
        )
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "resolver_auto_register_exists",
                dpp_id=str(dpp.id),
                identifier=identifier,
            )
            return

        # Build public DPP URL — determine tenant slug
        tenant_slug = getattr(dpp, "tenant_slug", None)
        if not tenant_slug:
            # Look up tenant slug from DB
            from app.db.models import Tenant

            tenant_result = await self._session.execute(
                select(Tenant.slug).where(Tenant.id == tenant_id)
            )
            tenant_slug = tenant_result.scalar_one_or_none() or "default"

        href = f"{base_url.rstrip('/')}/api/v1/public/{tenant_slug}/dpps/{dpp.id}"

        link = ResolverLink(
            tenant_id=tenant_id,
            identifier=identifier,
            link_type=link_type,
            href=href,
            media_type="application/json",
            title=f"Digital Product Passport for {gtin}",
            hreflang="en",
            priority=100,
            dpp_id=dpp.id,
            active=True,
            created_by_subject=created_by,
        )
        self._session.add(link)
        await self._session.flush()

        logger.info(
            "resolver_auto_register_created",
            dpp_id=str(dpp.id),
            identifier=identifier,
            href=href,
        )
