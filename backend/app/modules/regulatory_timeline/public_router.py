"""Public router for verified DPP regulatory timeline."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from app.core.config import get_settings
from app.db.session import DbSession
from app.modules.regulatory_timeline.schemas import (
    RegulatoryTimelineResponse,
    RegulatoryTimelineTrackFilter,
)
from app.modules.regulatory_timeline.service import (
    RegulatoryTimelineService,
    RegulatoryTimelineUnavailableError,
)

router = APIRouter()


def _server_timing_value(started_at: datetime) -> str:
    elapsed_ms = max(0, int((datetime.now(UTC) - started_at).total_seconds() * 1_000))
    return f"regulatory_timeline;dur={elapsed_ms}"


def _etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    if not if_none_match:
        return False

    candidates = [candidate.strip() for candidate in if_none_match.split(",") if candidate.strip()]
    normalized_current = current_etag.removeprefix("W/").strip()

    for candidate in candidates:
        if candidate == "*":
            return True
        normalized_candidate = candidate.removeprefix("W/").strip()
        if normalized_candidate == normalized_current:
            return True

    return False


@router.get("/landing/regulatory-timeline", response_model=RegulatoryTimelineResponse)
async def get_public_regulatory_timeline(
    db: DbSession,
    response: Response,
    track: RegulatoryTimelineTrackFilter = Query(default="all"),
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
) -> RegulatoryTimelineResponse | Response:
    """Get latest verified public timeline with stale-while-refresh behavior."""
    request_started_at = datetime.now(UTC)
    settings = get_settings()
    service = RegulatoryTimelineService(db)

    try:
        payload = await service.get_latest_timeline(track=track)
    except RegulatoryTimelineUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    cache_control = (
        settings.regulatory_timeline_cache_control_stale
        if payload.source_status == "stale"
        else settings.regulatory_timeline_cache_control_fresh
    )
    etag = f'"{payload.digest_sha256}"'
    server_timing = _server_timing_value(request_started_at)

    if _etag_matches(if_none_match, etag):
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "Cache-Control": cache_control,
                "ETag": etag,
                "Server-Timing": server_timing,
            },
        )

    response.headers["Cache-Control"] = cache_control
    response.headers["ETag"] = etag
    response.headers["Server-Timing"] = server_timing
    return payload
