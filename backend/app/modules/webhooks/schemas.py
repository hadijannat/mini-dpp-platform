"""Pydantic schemas for webhook subscriptions and deliveries."""

import ipaddress
import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

WebhookEventType = Literal[
    "DPP_CREATED",
    "DPP_PUBLISHED",
    "DPP_ARCHIVED",
    "DPP_EXPORTED",
    "EPCIS_CAPTURED",
]

ALL_WEBHOOK_EVENTS: list[str] = [
    "DPP_CREATED",
    "DPP_PUBLISHED",
    "DPP_ARCHIVED",
    "DPP_EXPORTED",
    "EPCIS_CAPTURED",
]

# Patterns for hostnames that must never receive webhook deliveries
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


def _reject_internal_urls(v: HttpUrl) -> HttpUrl:
    """Reject URLs targeting private/internal addresses (SSRF protection)."""
    host = v.host
    if not host:
        raise ValueError("URL must include a hostname")

    host_clean = host.strip("[]")

    if _BLOCKED_HOSTS.match(host_clean):
        raise ValueError("Webhook URLs must not target private or internal addresses")

    # Also check via ipaddress for any IP literal we might have missed
    try:
        ip = ipaddress.ip_address(host_clean)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Webhook URLs must not target private or internal addresses")
    except ValueError as exc:
        if "private" in str(exc) or "internal" in str(exc):
            raise
        # Not an IP literal — that's fine, it's a hostname

    return v


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[WebhookEventType] = Field(..., min_length=1)

    @field_validator("url")
    @classmethod
    def reject_internal_urls(cls, v: HttpUrl) -> HttpUrl:
        return _reject_internal_urls(v)


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: list[str]
    active: bool
    created_by_subject: str
    created_at: datetime
    updated_at: datetime


class WebhookUpdate(BaseModel):
    url: HttpUrl | None = None
    events: list[WebhookEventType] | None = None
    active: bool | None = None

    @field_validator("url")
    @classmethod
    def reject_internal_urls(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is None:
            return v
        return _reject_internal_urls(v)


class DeliveryLogResponse(BaseModel):
    id: UUID
    subscription_id: UUID
    event_type: str
    payload: dict[str, Any]
    http_status: int | None
    response_body: str | None
    attempt: int
    success: bool
    error_message: str | None
    created_at: datetime


class WebhookTestRequest(BaseModel):
    """Request to send a test payload to verify webhook connectivity."""

    pass
