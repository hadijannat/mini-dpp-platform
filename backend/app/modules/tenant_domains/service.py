"""Service layer for tenant-managed resolver domains."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TenantDomain, TenantDomainStatus

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[a-z0-9-]{1,63}\.)*[a-z0-9-]{1,63}$",
    re.IGNORECASE,
)


class TenantDomainError(ValueError):
    """Raised for invalid tenant domain operations."""


class TenantDomainService:
    """CRUD and lookup operations for resolver hostnames."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def normalize_hostname(hostname: str) -> str:
        """Normalize and validate a hostname."""
        raw = hostname.strip().lower().rstrip(".")
        if not raw:
            raise TenantDomainError("hostname is required")
        if "://" in raw:
            raise TenantDomainError("hostname must not include scheme")
        if "/" in raw or "?" in raw or "#" in raw:
            raise TenantDomainError("hostname must not include path/query/fragment")
        if ":" in raw:
            raise TenantDomainError("hostname must not include port")
        if len(raw) > 253:
            raise TenantDomainError("hostname is too long")
        if not _HOSTNAME_RE.fullmatch(raw):
            raise TenantDomainError("hostname is not a valid DNS hostname")
        for label in raw.split("."):
            if label.startswith("-") or label.endswith("-"):
                raise TenantDomainError("hostname labels cannot start or end with '-'")
        return raw

    async def list_domains(self, tenant_id: UUID) -> list[TenantDomain]:
        result = await self._session.execute(
            select(TenantDomain)
            .where(TenantDomain.tenant_id == tenant_id)
            .order_by(TenantDomain.is_primary.desc(), TenantDomain.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_domain(self, domain_id: UUID, tenant_id: UUID) -> TenantDomain | None:
        result = await self._session.execute(
            select(TenantDomain).where(
                TenantDomain.id == domain_id,
                TenantDomain.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_domain(
        self,
        *,
        tenant_id: UUID,
        created_by: str,
        hostname: str,
        is_primary: bool,
    ) -> TenantDomain:
        if is_primary:
            raise TenantDomainError("pending domains cannot be marked as primary")

        normalized = self.normalize_hostname(hostname)
        row = TenantDomain(
            tenant_id=tenant_id,
            hostname=normalized,
            status=TenantDomainStatus.PENDING,
            is_primary=is_primary,
            created_by_subject=created_by,
        )
        self._session.add(row)
        await self._session.flush()

        return row

    async def update_domain(
        self,
        *,
        domain_id: UUID,
        tenant_id: UUID,
        hostname: str | None,
        status: TenantDomainStatus | None,
        is_primary: bool | None,
        verification_method: str | None,
    ) -> TenantDomain | None:
        row = await self.get_domain(domain_id, tenant_id)
        if row is None:
            return None

        if hostname is not None:
            row.hostname = self.normalize_hostname(hostname)

        if status is not None:
            row.status = status
            if status == TenantDomainStatus.ACTIVE:
                row.verified_at = datetime.now(UTC)
                row.verification_method = verification_method or row.verification_method or "manual"
            elif status == TenantDomainStatus.DISABLED:
                row.is_primary = False

        if verification_method is not None:
            row.verification_method = verification_method or None

        if is_primary is not None:
            if is_primary and row.status != TenantDomainStatus.ACTIVE:
                raise TenantDomainError("only active domains can be marked as primary")
            row.is_primary = is_primary
            if is_primary:
                await self._unset_other_primaries(tenant_id=tenant_id, keep_id=row.id)

        await self._session.flush()
        return row

    async def delete_domain(self, *, domain_id: UUID, tenant_id: UUID) -> bool:
        row = await self.get_domain(domain_id, tenant_id)
        if row is None:
            return False
        if row.status == TenantDomainStatus.ACTIVE:
            raise TenantDomainError("active domains must be disabled before deletion")
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def resolve_active_tenant_by_hostname(self, hostname: str) -> UUID | None:
        normalized = self.normalize_hostname(hostname)
        result = await self._session.execute(
            select(TenantDomain.tenant_id).where(
                TenantDomain.hostname == normalized,
                TenantDomain.status == TenantDomainStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_primary_active_domain(self, tenant_id: UUID) -> TenantDomain | None:
        result = await self._session.execute(
            select(TenantDomain).where(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.status == TenantDomainStatus.ACTIVE,
                TenantDomain.is_primary.is_(True),
            )
        )
        primary = result.scalar_one_or_none()
        if primary is not None:
            return primary
        fallback = await self._session.execute(
            select(TenantDomain)
            .where(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.status == TenantDomainStatus.ACTIVE,
            )
            .order_by(TenantDomain.created_at.desc())
            .limit(1)
        )
        return fallback.scalar_one_or_none()

    async def _unset_other_primaries(self, *, tenant_id: UUID, keep_id: UUID) -> None:
        result = await self._session.execute(
            select(TenantDomain).where(
                TenantDomain.tenant_id == tenant_id,
                TenantDomain.id != keep_id,
                TenantDomain.is_primary.is_(True),
            )
        )
        for row in result.scalars().all():
            row.is_primary = False
