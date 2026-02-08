"""Pydantic schemas for GS1 Digital Link resolver module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LinkType(str, Enum):
    """GS1 link relation types for Digital Link resolver entries."""

    HAS_DPP = "gs1:hasDigitalProductPassport"
    PIP = "gs1:pip"
    CERTIFICATION_INFO = "gs1:certificationInfo"
    EPIL = "gs1:epil"
    DEFAULT_LINK = "gs1:defaultLink"
    PRODUCT_SUSTAINABILITY_INFO = "gs1:productSustainabilityInfo"
    QUICK_START_GUIDE = "gs1:quickStartGuide"
    SUPPORT = "gs1:support"
    REGISTRATION = "gs1:registration"
    RECALL_STATUS = "gs1:recallStatus"
    IEC61406_ID = "iec61406:identificationLink"


class ResolverLinkCreate(BaseModel):
    """Input schema for creating a resolver link."""

    identifier: str = Field(
        ...,
        description="GS1 identifier stem, e.g. '01/09520123456788/21/SERIAL001'",
        min_length=1,
    )
    link_type: LinkType = Field(
        default=LinkType.HAS_DPP,
        description="GS1 link relation type",
    )
    href: str = Field(
        ...,
        description="Target URL the link resolves to",
        min_length=1,
    )
    media_type: str = Field(
        default="application/json",
        description="MIME type of the target resource",
    )
    title: str = Field(
        default="",
        description="Human-readable title for the link",
    )
    hreflang: str = Field(
        default="en",
        description="Language of the target resource (BCP 47)",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Link priority (higher = preferred)",
    )
    dpp_id: UUID | None = Field(
        default=None,
        description="Associated DPP ID (optional)",
    )


class ResolverLinkUpdate(BaseModel):
    """Partial update schema for resolver links."""

    href: str | None = None
    media_type: str | None = None
    title: str | None = None
    hreflang: str | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    active: bool | None = None


class ResolverLinkResponse(BaseModel):
    """Response schema for resolver links."""

    id: UUID
    tenant_id: UUID
    identifier: str
    link_type: str
    href: str
    media_type: str
    title: str
    hreflang: str
    priority: int
    dpp_id: UUID | None
    active: bool
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class LinksetLink(BaseModel):
    """Single link within an RFC 9264 linkset."""

    href: str
    type: str | None = None
    title: str | None = None
    hreflang: str | None = None


class LinksetResponse(BaseModel):
    """RFC 9264 linkset JSON response."""

    anchor: str
    linkset: dict[str, list[LinksetLink]]


class ResolverDescriptionResponse(BaseModel):
    """GS1 resolver description document (.well-known/gs1resolver)."""

    name: str
    resolverRoot: str
    supportedLinkTypes: list[dict[str, Any]]
    supportedContextValuesEnumerated: list[str] = Field(default_factory=list)
