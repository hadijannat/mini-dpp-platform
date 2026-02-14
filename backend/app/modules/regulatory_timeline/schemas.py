"""Schemas for public regulatory timeline endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RegulatoryTimelineTrack = Literal["regulation", "standards"]
RegulatoryTimelineTrackFilter = Literal["all", "regulation", "standards"]
RegulatoryTimelineSourceStatus = Literal["fresh", "stale"]
RegulatoryTimelineEventStatus = Literal["past", "today", "upcoming"]
RegulatoryTimelineDatePrecision = Literal["day", "month"]
RegulatoryTimelineVerificationMethod = Literal["source-hash", "content-match", "manual"]
RegulatoryTimelineConfidence = Literal["high", "medium", "low"]


class RegulatoryTimelineSource(BaseModel):
    """Official citation used to verify a timeline event."""

    label: str
    url: str
    publisher: str
    retrieved_at: str
    sha256: str | None = None


class RegulatoryTimelineVerification(BaseModel):
    """Verification metadata for a timeline event."""

    checked_at: str
    method: RegulatoryTimelineVerificationMethod
    confidence: RegulatoryTimelineConfidence


class RegulatoryTimelineEvent(BaseModel):
    """Single verified timeline milestone."""

    id: str
    date: str
    date_precision: RegulatoryTimelineDatePrecision
    track: RegulatoryTimelineTrack
    title: str
    plain_summary: str
    audience_tags: list[str] = Field(default_factory=list)
    status: RegulatoryTimelineEventStatus
    verified: bool
    verification: RegulatoryTimelineVerification
    sources: list[RegulatoryTimelineSource] = Field(default_factory=list)


class RegulatoryTimelineResponse(BaseModel):
    """Public response contract for landing timeline."""

    generated_at: str
    fetched_at: str
    source_status: RegulatoryTimelineSourceStatus
    refresh_sla_seconds: int
    digest_sha256: str
    events: list[RegulatoryTimelineEvent]
