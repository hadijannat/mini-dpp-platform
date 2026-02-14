"""Service layer for public CIRPASS story feed and leaderboard."""

from __future__ import annotations

import asyncio
import hashlib
import re
import secrets
import time
from collections import deque
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import jwt
from sqlalchemy import asc, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import CirpassLeaderboardEntry, CirpassStorySnapshot
from app.db.session import get_background_session
from app.modules.cirpass.parser import CirpassParseError, CirpassSourceParser, iso_now
from app.modules.cirpass.schemas import (
    CirpassLeaderboardEntryResponse,
    CirpassLeaderboardResponse,
    CirpassLeaderboardSubmitRequest,
    CirpassLeaderboardSubmitResponse,
    CirpassSessionResponse,
    CirpassStoryFeedResponse,
)

logger = get_logger(__name__)

NICKNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,20}$")
_HOURLY_LIMIT_PER_SID = 3
_DAILY_LIMIT_PER_IP = 20

_refresh_lock = asyncio.Lock()
_refresh_task: asyncio.Task[None] | None = None
_sid_event_window: dict[str, deque[float]] = {}
_ip_event_window: dict[str, deque[float]] = {}


class CirpassUnavailableError(RuntimeError):
    """Raised when no story snapshot can be served."""


class CirpassRateLimitError(RuntimeError):
    """Raised when submission rate limits are exceeded."""


class CirpassSessionError(RuntimeError):
    """Raised for invalid or expired CIRPASS session token usage."""


class CirpassValidationError(RuntimeError):
    """Raised when client payload fails validation rules."""


class CirpassLabService:
    """Business logic for CIRPASS feed refresh/session/leaderboard."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self._parser = CirpassSourceParser(self.settings.cirpass_results_url)

    async def get_latest_stories(self) -> CirpassStoryFeedResponse:
        snapshot = await self._load_latest_snapshot()

        if snapshot is None:
            try:
                return await self.refresh_stories()
            except Exception as exc:  # noqa: BLE001
                logger.warning("cirpass_initial_refresh_failed", error=str(exc))
                raise CirpassUnavailableError(
                    "Latest CIRPASS stories are temporarily unavailable. Please retry shortly."
                ) from exc

        status = "fresh"
        if self._is_snapshot_stale(snapshot):
            status = "stale"
            schedule_cirpass_refresh()

        return self._snapshot_to_feed(snapshot, source_status=status)

    async def refresh_stories(self) -> CirpassStoryFeedResponse:
        async with _refresh_lock:
            timeout = httpx.Timeout(20.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                parsed = await self._parser.fetch_latest_feed(client)

            payload = {"levels": [level.model_dump() for level in parsed.levels]}
            snapshot = await self._upsert_snapshot(
                version=parsed.version,
                release_date=parsed.release_date,
                source_url=parsed.source_url,
                zenodo_record_url=parsed.zenodo_record_url,
                zenodo_record_id=parsed.zenodo_record_id,
                stories_json=payload,
            )
            return self._snapshot_to_feed(snapshot, source_status="fresh")

    async def create_session(self, user_agent: str) -> CirpassSessionResponse:
        issued_at = int(time.time())
        expires_at = issued_at + self.settings.cirpass_session_ttl_seconds
        sid = secrets.token_hex(16)

        payload = {
            "sid": sid,
            "iat": issued_at,
            "exp": expires_at,
            "ua_hash": self._hash_user_agent(user_agent),
        }
        token = jwt.encode(
            payload,
            self.settings.cirpass_session_token_secret,
            algorithm="HS256",
        )

        return CirpassSessionResponse(
            session_token=token,
            expires_at=datetime.fromtimestamp(expires_at, tz=UTC).isoformat(),
        )

    async def get_leaderboard(
        self,
        version: str | None,
        limit: int | None,
    ) -> CirpassLeaderboardResponse:
        effective_limit = self._resolve_limit(limit)
        effective_version = version.strip() if version else ""

        if not effective_version:
            snapshot = await self._load_latest_snapshot()
            effective_version = snapshot.version if snapshot is not None else "V3.1"

        rows = await self._load_ranked_entries(effective_version)
        entries = [
            CirpassLeaderboardEntryResponse(
                rank=idx,
                nickname=row.nickname,
                score=row.score,
                completion_seconds=row.completion_seconds,
                version=row.version,
                created_at=row.created_at.isoformat(),
            )
            for idx, row in enumerate(rows[:effective_limit], start=1)
        ]
        return CirpassLeaderboardResponse(version=effective_version, entries=entries)

    async def submit_score(
        self,
        payload: CirpassLeaderboardSubmitRequest,
        user_agent: str,
        client_ip: str,
    ) -> CirpassLeaderboardSubmitResponse:
        nickname = payload.nickname.strip()
        if not NICKNAME_PATTERN.fullmatch(nickname):
            raise CirpassValidationError(
                "Nickname must match ^[A-Za-z0-9_-]{3,20}$"
            )

        claims = self._decode_session_token(payload.session_token)
        sid = str(claims["sid"])
        ua_hash = str(claims["ua_hash"])
        expected_hash = self._hash_user_agent(user_agent)
        if ua_hash != expected_hash:
            raise CirpassSessionError("Session token does not match current browser signature")

        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
        self._enforce_rate_limits(sid=sid, ip_hash=ip_hash)

        cutoff = datetime.now(UTC) - timedelta(days=90)
        await self.db.execute(
            delete(CirpassLeaderboardEntry).where(CirpassLeaderboardEntry.created_at < cutoff)
        )

        existing_result = await self.db.execute(
            select(CirpassLeaderboardEntry).where(
                CirpassLeaderboardEntry.sid == sid,
                CirpassLeaderboardEntry.version == payload.version,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing is None:
            entry = CirpassLeaderboardEntry(
                sid=sid,
                ip_hash=ip_hash,
                nickname=nickname,
                score=payload.score,
                completion_seconds=payload.completion_seconds,
                version=payload.version,
            )
            self.db.add(entry)
            await self.db.flush()
        else:
            should_replace = (
                payload.score > existing.score
                or (
                    payload.score == existing.score
                    and payload.completion_seconds < existing.completion_seconds
                )
            )
            if should_replace:
                existing.score = payload.score
                existing.completion_seconds = payload.completion_seconds
                existing.nickname = nickname
                existing.ip_hash = ip_hash
                await self.db.flush()

        ranked_rows = await self._load_ranked_entries(payload.version)
        rank: int | None = None
        best_score: int | None = None

        for idx, row in enumerate(ranked_rows, start=1):
            if row.sid == sid and row.version == payload.version:
                rank = idx
                best_score = row.score
                break

        return CirpassLeaderboardSubmitResponse(
            accepted=True,
            rank=rank,
            best_score=best_score,
            version=payload.version,
        )

    async def _upsert_snapshot(
        self,
        *,
        version: str,
        release_date: str | None,
        source_url: str,
        zenodo_record_url: str,
        zenodo_record_id: str | None,
        stories_json: dict[str, Any],
    ) -> CirpassStorySnapshot:
        existing_result = await self.db.execute(
            select(CirpassStorySnapshot).where(
                CirpassStorySnapshot.version == version,
                CirpassStorySnapshot.zenodo_record_url == zenodo_record_url,
            )
        )
        existing = existing_result.scalar_one_or_none()

        parsed_release_date: date | None = None
        if release_date:
            try:
                parsed_release_date = date.fromisoformat(release_date)
            except ValueError:
                parsed_release_date = None

        if existing is None:
            existing = CirpassStorySnapshot(
                version=version,
                release_date=parsed_release_date,
                source_url=source_url,
                zenodo_record_url=zenodo_record_url,
                zenodo_record_id=zenodo_record_id,
                stories_json=stories_json,
                fetched_at=datetime.now(UTC),
            )
            self.db.add(existing)
        else:
            existing.release_date = parsed_release_date
            existing.source_url = source_url
            existing.zenodo_record_id = zenodo_record_id
            existing.stories_json = stories_json
            existing.fetched_at = datetime.now(UTC)

        await self.db.flush()
        return existing

    async def _load_latest_snapshot(self) -> CirpassStorySnapshot | None:
        result = await self.db.execute(
            select(CirpassStorySnapshot).order_by(desc(CirpassStorySnapshot.fetched_at)).limit(1)
        )
        return result.scalar_one_or_none()

    async def _load_ranked_entries(self, version: str) -> list[CirpassLeaderboardEntry]:
        result = await self.db.execute(
            select(CirpassLeaderboardEntry)
            .where(CirpassLeaderboardEntry.version == version)
            .order_by(
                desc(CirpassLeaderboardEntry.score),
                asc(CirpassLeaderboardEntry.completion_seconds),
                asc(CirpassLeaderboardEntry.created_at),
            )
        )
        return list(result.scalars().all())

    def _snapshot_to_feed(
        self,
        snapshot: CirpassStorySnapshot,
        *,
        source_status: str,
    ) -> CirpassStoryFeedResponse:
        raw_levels = snapshot.stories_json.get("levels") if isinstance(snapshot.stories_json, dict) else []
        levels = raw_levels if isinstance(raw_levels, list) else []

        return CirpassStoryFeedResponse(
            version=snapshot.version,
            release_date=snapshot.release_date.isoformat() if snapshot.release_date else None,
            source_url=snapshot.source_url,
            zenodo_record_url=snapshot.zenodo_record_url,
            source_status="stale" if source_status == "stale" else "fresh",
            generated_at=iso_now(),
            fetched_at=snapshot.fetched_at.isoformat(),
            levels=levels,
        )

    def _is_snapshot_stale(self, snapshot: CirpassStorySnapshot) -> bool:
        fetched_at = snapshot.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)
        age_seconds = (datetime.now(UTC) - fetched_at.astimezone(UTC)).total_seconds()
        return age_seconds > self.settings.cirpass_refresh_ttl_seconds

    def _decode_session_token(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self.settings.cirpass_session_token_secret,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError as exc:
            raise CirpassSessionError("Session token has expired") from exc
        except jwt.PyJWTError as exc:
            raise CirpassSessionError("Invalid session token") from exc

        if not isinstance(claims, dict) or "sid" not in claims or "ua_hash" not in claims:
            raise CirpassSessionError("Session token payload is invalid")
        return claims

    def _enforce_rate_limits(self, *, sid: str, ip_hash: str) -> None:
        now = time.time()

        sid_window = _sid_event_window.setdefault(sid, deque())
        self._trim_window(sid_window, now - 3600)
        if len(sid_window) >= _HOURLY_LIMIT_PER_SID:
            raise CirpassRateLimitError("Submission limit reached: max 3 submissions per hour")

        ip_window = _ip_event_window.setdefault(ip_hash, deque())
        self._trim_window(ip_window, now - 86400)
        if len(ip_window) >= _DAILY_LIMIT_PER_IP:
            raise CirpassRateLimitError("Submission limit reached: max 20 submissions per day")

        sid_window.append(now)
        ip_window.append(now)

    def _trim_window(self, window: deque[float], threshold: float) -> None:
        while window and window[0] < threshold:
            window.popleft()

    def _resolve_limit(self, requested: int | None) -> int:
        if requested is None:
            return self.settings.cirpass_leaderboard_limit_default
        return max(1, min(requested, self.settings.cirpass_leaderboard_limit_max))

    def _hash_user_agent(self, user_agent: str) -> str:
        normalized = (user_agent or "unknown-user-agent").strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _refresh_in_background() -> None:
    try:
        async with get_background_session() as db:
            service = CirpassLabService(db)
            await service.refresh_stories()
    except CirpassParseError as exc:
        logger.warning("cirpass_background_refresh_parse_failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("cirpass_background_refresh_failed", error=str(exc))


def schedule_cirpass_refresh() -> None:
    """Schedule stale-source refresh if one is not already running."""
    global _refresh_task  # noqa: PLW0603

    loop = asyncio.get_running_loop()
    if _refresh_task and not _refresh_task.done():
        return

    _refresh_task = loop.create_task(_refresh_in_background())
