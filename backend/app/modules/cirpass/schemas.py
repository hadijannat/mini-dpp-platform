"""Schemas for public CIRPASS lab endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CirpassLevelKey = Literal["create", "access", "update", "transfer", "deactivate"]
CirpassSourceStatus = Literal["fresh", "stale"]
CirpassLabMode = Literal["mock", "live"]
CirpassLabVariant = Literal["happy", "unauthorized", "not_found"]
CirpassLabTelemetryEventType = Literal[
    "step_view",
    "step_submit",
    "hint",
    "mode_switch",
    "reset_story",
    "reset_all",
]
CirpassLabTelemetryResult = Literal["success", "error", "info"]


def _default_step_variants() -> list[CirpassLabVariant]:
    return ["happy"]


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


class CirpassLabReferenceResponse(BaseModel):
    """Citation metadata for scenario narratives."""

    label: str
    ref: str


class CirpassLabUiActionResponse(BaseModel):
    """Learner-facing UI action descriptor."""

    label: str
    kind: Literal["click", "form", "scan", "select"]


class CirpassLabApiCallResponse(BaseModel):
    """API interaction metadata for under-the-hood inspector."""

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    auth: Literal["none", "user", "service"] = "none"
    request_example: dict[str, Any] | None = None
    expected_status: int | None = None
    response_example: dict[str, Any] | None = None


class CirpassLabStepCheckResponse(BaseModel):
    """Validation check metadata attached to a step."""

    type: Literal["jsonpath", "jmespath", "status", "schema"]
    expression: str | None = None
    expected: str | int | float | bool | dict[str, Any] | list[Any] | None = None


class CirpassLabArtifactsResponse(BaseModel):
    """Optional artifact snapshots displayed in diff inspector."""

    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    diff_hint: str | None = None


class CirpassLabPolicyInspectorResponse(BaseModel):
    """Optional policy/authorization hints for a step."""

    required_role: str | None = None
    opa_policy: str | None = None
    expected_decision: Literal["allow", "deny", "mask"] | None = None
    note: str | None = None


class CirpassLabStepResponse(BaseModel):
    """Data-driven CIRPASS story step consumed by the scenario runner."""

    id: str
    level: CirpassLevelKey
    title: str
    actor: str
    intent: str
    explanation_md: str
    ui_action: CirpassLabUiActionResponse | None = None
    api: CirpassLabApiCallResponse | None = None
    artifacts: CirpassLabArtifactsResponse | None = None
    checks: list[CirpassLabStepCheckResponse] = Field(default_factory=list)
    policy: CirpassLabPolicyInspectorResponse | None = None
    variants: list[CirpassLabVariant] = Field(default_factory=_default_step_variants)


class CirpassLabStoryResponse(BaseModel):
    """Scenario story bundle containing ordered executable steps."""

    id: str
    title: str
    summary: str
    personas: list[str]
    learning_goals: list[str] = Field(default_factory=list)
    preconditions_md: str | None = None
    references: list[CirpassLabReferenceResponse] = Field(default_factory=list)
    version: str | None = None
    last_reviewed: str | None = None
    steps: list[CirpassLabStepResponse]


class CirpassLabFeatureFlagsResponse(BaseModel):
    """Feature-flag projection used by lab clients."""

    scenario_engine_enabled: bool
    live_mode_enabled: bool
    inspector_enabled: bool


class CirpassLabManifestResponse(BaseModel):
    """Resolved CIRPASS lab manifest served by public API."""

    manifest_version: str
    story_version: str
    generated_at: str
    source_status: Literal["fresh", "fallback"]
    stories: list[CirpassLabStoryResponse]
    feature_flags: CirpassLabFeatureFlagsResponse


class CirpassLabEventRequest(BaseModel):
    """Anonymized telemetry payload sent from the public lab client."""

    session_token: str = Field(min_length=20, max_length=4096)
    story_id: str = Field(min_length=1, max_length=64)
    step_id: str = Field(min_length=1, max_length=64)
    event_type: CirpassLabTelemetryEventType
    mode: CirpassLabMode = "mock"
    variant: CirpassLabVariant = "happy"
    result: CirpassLabTelemetryResult = "info"
    latency_ms: int | None = Field(default=None, ge=0, le=600_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CirpassLabEventResponse(BaseModel):
    """Telemetry ingestion acknowledgement."""

    accepted: bool
    event_id: str
    stored_at: str
