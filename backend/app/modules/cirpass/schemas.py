"""Schemas for public CIRPASS lab endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CirpassLevelKey = Literal["create", "access", "update", "transfer", "deactivate"]
CirpassSourceStatus = Literal["fresh", "stale"]


class CirpassStoryResponse(BaseModel):
    """Single user story summary extracted from source documents."""

    id: str
    title: str
    summary: str
    technical_note: str | None = None


class CirpassLevelResponse(BaseModel):
    """Stories mapped to one simulator lifecycle level."""

    level: CirpassLevelKey
    label: str
    objective: str
    stories: list[CirpassStoryResponse]


class CirpassStoryFeedResponse(BaseModel):
    """Latest normalized CIRPASS story feed for simulator consumption."""

    version: str
    release_date: str | None = None
    source_url: str
    zenodo_record_url: str
    source_status: CirpassSourceStatus
    generated_at: str
    fetched_at: str
    levels: list[CirpassLevelResponse]


class CirpassSessionResponse(BaseModel):
    """Public anonymous session token used for leaderboard submissions."""

    session_token: str
    expires_at: str


class CirpassLeaderboardEntryResponse(BaseModel):
    """Public leaderboard row."""

    rank: int
    nickname: str
    score: int
    completion_seconds: int
    version: str
    created_at: str


class CirpassLeaderboardResponse(BaseModel):
    """Leaderboard listing for a specific or latest version."""

    version: str
    entries: list[CirpassLeaderboardEntryResponse]


class CirpassLeaderboardSubmitRequest(BaseModel):
    """Payload for public score submissions."""

    session_token: str = Field(min_length=20, max_length=4096)
    nickname: str = Field(min_length=3, max_length=20)
    score: int = Field(ge=0)
    completion_seconds: int = Field(ge=0)
    version: str = Field(min_length=1, max_length=32)


class CirpassLeaderboardSubmitResponse(BaseModel):
    """Submission result and current leaderboard rank snapshot."""

    accepted: bool
    rank: int | None = None
    best_score: int | None = None
    version: str


class ParsedCirpassFeed(BaseModel):
    """Internal parsed feed model used by parser/service boundary."""

    version: str
    release_date: str | None = None
    source_url: str
    zenodo_record_url: str
    zenodo_record_id: str | None = None
    levels: list[CirpassLevelResponse]

    model_config = ConfigDict(frozen=True)
