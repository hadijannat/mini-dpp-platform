"""Pydantic schemas for audit trail API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    """Single audit event in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID | None = None
    subject: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    decision: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata_: dict[str, Any] | None = None
    created_at: datetime

    # Hash chain fields (nullable — only present when crypto columns exist)
    event_hash: str | None = None
    prev_event_hash: str | None = None
    chain_sequence: int | None = None


class AuditEventListResponse(BaseModel):
    """Paginated list of audit events."""

    items: list[AuditEventResponse]
    total: int
    page: int
    page_size: int


class ChainVerificationResponse(BaseModel):
    """Result of verifying the audit hash chain for a tenant."""

    is_valid: bool
    verified_count: int
    first_break_at: int | None = None
    errors: list[str]
    tenant_id: UUID


class EventVerificationResponse(BaseModel):
    """Result of verifying a single audit event."""

    is_valid: bool
    event_id: UUID
    event_hash: str | None = None


class AnchorResponse(BaseModel):
    """Result of a Merkle anchor operation."""

    merkle_root: str
    event_count: int
    first_sequence: int
    last_sequence: int
    signature: str | None = None
    tsa_token_present: bool = False
    tenant_id: UUID
