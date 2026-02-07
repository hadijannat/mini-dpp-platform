"""Pydantic schemas for the digital thread event store."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import LifecyclePhase


class ThreadEventCreate(BaseModel):
    """Input for recording a digital thread event."""

    phase: LifecyclePhase = Field(description="Product lifecycle phase")
    event_type: str = Field(
        min_length=1,
        max_length=100,
        description="Event type, e.g. dpp_created, material_sourced, assembled",
    )
    source: str = Field(
        min_length=1,
        max_length=255,
        description="System or organization that emitted the event",
    )
    source_event_id: str | None = Field(
        default=None,
        max_length=255,
        description="External event correlation ID",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data",
    )
    parent_event_id: UUID | None = Field(
        default=None,
        description="Causal parent event for event chains",
    )


class ThreadEventResponse(BaseModel):
    """Full event output."""

    id: UUID
    dpp_id: UUID
    phase: LifecyclePhase
    event_type: str
    source: str
    source_event_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_event_id: UUID | None = None
    created_by_subject: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EventQuery(BaseModel):
    """Query parameters for event listing."""

    dpp_id: UUID
    phase: LifecyclePhase | None = None
    event_type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class TimelinePhaseGroup(BaseModel):
    """Events within a single lifecycle phase."""

    phase: LifecyclePhase
    events: list[ThreadEventResponse]
    count: int


class LifecycleTimeline(BaseModel):
    """Grouped timeline response for a DPP's digital thread."""

    dpp_id: UUID
    phases: dict[str, list[ThreadEventResponse]]
    total_events: int
