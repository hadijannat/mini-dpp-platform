"""Schemas for tenant-managed resolver domains."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import TenantDomainStatus


class TenantDomainCreateRequest(BaseModel):
    """Create request for a tenant-managed resolver domain."""

    hostname: str = Field(..., min_length=1, max_length=255)
    is_primary: bool = False


class TenantDomainUpdateRequest(BaseModel):
    """Patch request for mutable tenant domain fields."""

    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    status: TenantDomainStatus | None = None
    is_primary: bool | None = None
    verification_method: str | None = Field(default=None, max_length=32)


class TenantDomainResponse(BaseModel):
    """Response for tenant domain records."""

    id: UUID
    tenant_id: UUID
    hostname: str
    status: TenantDomainStatus
    is_primary: bool
    verification_method: str | None
    verified_at: datetime | None
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class TenantDomainListResponse(BaseModel):
    """Paginated-ish list response for tenant domains."""

    items: list[TenantDomainResponse]
    count: int
