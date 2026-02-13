"""Pydantic schemas for GS1 Digital Link resolver module."""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_ALLOWED_HREF_SCHEMES = {"http", "https"}

# Hostnames that must never appear in resolver link targets (SSRF protection)
_BLOCKED_HOSTS = re.compile(
    r"^("
    r"localhost"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3}"
    r"|0\.0\.0\.0"
    r"|\[?::1\]?"
    r"|\[?fe80:.*\]?"
    r"|\[?f[cd][0-9a-f]{2}:.*\]?"
    r")$",
    re.IGNORECASE,
)


def _reject_internal_urls(v: str) -> str:
    """Reject URLs targeting private/internal addresses (SSRF protection)."""
    parsed = urlparse(v)
    host = parsed.hostname
    if not host:
        raise ValueError("URL must include a hostname")

    host_clean = host.strip("[]")

    if _BLOCKED_HOSTS.match(host_clean):
        raise ValueError("Resolver link URLs must not target private or internal addresses")

    try:
        ip = ipaddress.ip_address(host_clean)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Resolver link URLs must not target private or internal addresses")
    except ValueError as exc:
        if "private" in str(exc) or "internal" in str(exc):
            raise
        # Not an IP literal — that's fine, it's a hostname

    return v


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

    @field_validator("href")
    @classmethod
    def validate_href(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme.lower() not in _ALLOWED_HREF_SCHEMES:
            raise ValueError(f"href must use http or https scheme, got '{parsed.scheme}'")
        return _reject_internal_urls(v)


class ResolverLinkUpdate(BaseModel):
    """Partial update schema for resolver links."""

    href: str | None = None
    media_type: str | None = None
    title: str | None = None
    hreflang: str | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
    active: bool | None = None

    @field_validator("href")
    @classmethod
    def validate_href(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme.lower() not in _ALLOWED_HREF_SCHEMES:
            raise ValueError(f"href must use http or https scheme, got '{parsed.scheme}'")
        return _reject_internal_urls(v)


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
    managed_by_system: bool
    source_data_carrier_id: UUID | None
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
