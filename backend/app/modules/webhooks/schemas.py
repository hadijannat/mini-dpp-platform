"""Pydantic schemas for webhook subscriptions and deliveries."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

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


class WebhookCreate(BaseModel):
    url: HttpUrl
    events: list[WebhookEventType] = Field(..., min_length=1)


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
