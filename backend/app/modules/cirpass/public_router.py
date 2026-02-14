"""Public router for CIRPASS story feed and gamified leaderboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.db.session import DbSession
from app.modules.cirpass.schemas import (
    CirpassLeaderboardResponse,
    CirpassLeaderboardSubmitRequest,
    CirpassLeaderboardSubmitResponse,
    CirpassSessionResponse,
    CirpassStoryFeedResponse,
)
from app.modules.cirpass.service import (
    CirpassLabService,
    CirpassRateLimitError,
    CirpassSessionError,
    CirpassUnavailableError,
    CirpassValidationError,
)

router = APIRouter(prefix="/cirpass")


@router.get("/stories/latest", response_model=CirpassStoryFeedResponse)
async def get_latest_cirpass_stories(db: DbSession, response: Response) -> CirpassStoryFeedResponse:
    """Get latest CIRPASS user-story feed with stale-while-refresh behavior."""
    service = CirpassLabService(db)
    try:
        payload = await service.get_latest_stories()
    except CirpassUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if payload.source_status == "stale":
        response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=300"
    else:
        response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=300"
    return payload


@router.post("/session", response_model=CirpassSessionResponse)
async def create_cirpass_session(request: Request, db: DbSession) -> CirpassSessionResponse:
    """Create anonymous signed browser session for public leaderboard submissions."""
    service = CirpassLabService(db)
    user_agent = request.headers.get("user-agent", "")
    return await service.create_session(user_agent=user_agent)


@router.get("/leaderboard", response_model=CirpassLeaderboardResponse)
async def get_cirpass_leaderboard(
    db: DbSession,
    version: str | None = Query(default=None, min_length=1, max_length=32),
    limit: int | None = Query(default=None, ge=1, le=100),
) -> CirpassLeaderboardResponse:
    """Read public leaderboard rows for a CIRPASS story version."""
    service = CirpassLabService(db)
    return await service.get_leaderboard(version=version, limit=limit)


@router.post("/leaderboard/submit", response_model=CirpassLeaderboardSubmitResponse)
async def submit_cirpass_leaderboard_score(
    payload: CirpassLeaderboardSubmitRequest,
    request: Request,
    db: DbSession,
) -> CirpassLeaderboardSubmitResponse:
    """Submit a pseudonymous public score for the CIRPASS simulator."""
    service = CirpassLabService(db)
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client and request.client.host else "0.0.0.0"

    try:
        return await service.submit_score(
            payload=payload,
            user_agent=user_agent,
            client_ip=client_ip,
        )
    except CirpassRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except CirpassSessionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except CirpassValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
