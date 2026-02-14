"""Service layer for public verified regulatory timeline snapshots."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from urllib.parse import urlparse

import httpx
import yaml
from prometheus_client import Counter, Histogram
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import RegulatoryTimelineSnapshot
from app.db.session import get_background_session
from app.modules.regulatory_timeline.schemas import (
    RegulatoryTimelineEvent,
    RegulatoryTimelineResponse,
    RegulatoryTimelineSourceStatus,
    RegulatoryTimelineTrack,
    RegulatoryTimelineTrackFilter,
)

logger = get_logger(__name__)

_REGULATION_ALLOWED_HOSTS = {
    "commission.europa.eu",
    "eur-lex.europa.eu",
    "environment.ec.europa.eu",
}

_STANDARDS_ALLOWED_HOSTS = {
    "cencenelec.eu",
    "www.cencenelec.eu",
    "iso.org",
    "www.iso.org",
    "gs1.org",
    "www.gs1.org",
    "iec.ch",
    "www.iec.ch",
    "etsi.org",
    "www.etsi.org",
}

_refresh_lock = asyncio.Lock()
_refresh_task: asyncio.Task[None] | None = None

_SEED_REPO_RELATIVE = Path("docs/public/regulatory-timeline/events.seed.yaml")
_SEED_PACKAGED_RELATIVE = Path("data/events.seed.yaml")

_METRIC_REFRESH_ATTEMPTS = "regulatory_timeline_refresh_attempts_total"
_METRIC_REFRESH_RESULTS = "regulatory_timeline_refresh_results_total"
_METRIC_REFRESH_DURATION = "regulatory_timeline_refresh_duration_seconds"
_METRIC_SOURCE_FETCH_RESULTS = "regulatory_timeline_source_fetch_results_total"
_METRIC_SERVED_SNAPSHOTS = "regulatory_timeline_served_snapshots_total"

_refresh_attempts_total = Counter(
    _METRIC_REFRESH_ATTEMPTS,
    "Total regulatory timeline refresh attempts grouped by mode and requested track.",
    ("mode", "track"),
)
_refresh_results_total = Counter(
    _METRIC_REFRESH_RESULTS,
    "Total regulatory timeline refresh outcomes grouped by mode/track/result.",
    ("mode", "track", "result"),
)
_refresh_duration_seconds = Histogram(
    _METRIC_REFRESH_DURATION,
    "Duration of regulatory timeline refresh operations in seconds.",
    ("mode", "track", "result"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 60),
)
_source_fetch_results_total = Counter(
    _METRIC_SOURCE_FETCH_RESULTS,
    "Per-source verification outcomes grouped by timeline track.",
    ("track", "result"),
)
_served_snapshots_total = Counter(
    _METRIC_SERVED_SNAPSHOTS,
    "Timeline responses served by freshness status and requested track.",
    ("source_status", "track"),
)


class RegulatoryTimelineUnavailableError(RuntimeError):
    """Raised when timeline data cannot be served."""


class RegulatoryTimelineValidationError(RuntimeError):
    """Raised when timeline seed or source validation fails."""


def iso_now() -> str:
    """UTC ISO helper used by service-level response generation."""
    return datetime.now(UTC).isoformat()


class RegulatoryTimelineService:
    """Business logic for verified timeline refresh and serving."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self._seed_path = self._resolve_seed_path(
            seed_path_override=self.settings.regulatory_timeline_seed_path,
        )

    @staticmethod
    def _resolve_seed_path(
        *,
        seed_path_override: str | None = None,
        module_path: Path | None = None,
        cwd: Path | None = None,
    ) -> Path:
        """Resolve timeline seed file with explicit, repo, then packaged fallback order."""
        resolved_module_path = (module_path or Path(__file__)).resolve()

        if seed_path_override:
            explicit_path = Path(seed_path_override).expanduser().resolve()
            if explicit_path.exists():
                return explicit_path
            logger.warning(
                "regulatory_timeline_seed_override_missing_falling_back",
                configured_path=str(explicit_path),
            )

        for ancestor in resolved_module_path.parents:
            candidate = (ancestor / _SEED_REPO_RELATIVE).resolve()
            if candidate.exists():
                return candidate

        packaged_candidate = (resolved_module_path.parent / _SEED_PACKAGED_RELATIVE).resolve()
        if packaged_candidate.exists():
            return packaged_candidate

        cwd_candidate = ((cwd or Path.cwd()) / _SEED_REPO_RELATIVE).resolve()
        if cwd_candidate.exists():
            return cwd_candidate

        return packaged_candidate

    async def get_latest_timeline(
        self,
        track: RegulatoryTimelineTrackFilter,
    ) -> RegulatoryTimelineResponse:
        """Read latest timeline snapshot with stale-while-refresh behavior."""
        snapshot = await self._load_latest_snapshot()

        if snapshot is None:
            try:
                async with _refresh_lock:
                    snapshot = await self._load_latest_snapshot()
                    if snapshot is None:
                        snapshot = await self._bootstrap_timeline_snapshot()
            except Exception as exc:  # noqa: BLE001
                logger.warning("regulatory_timeline_initial_refresh_failed", error=str(exc))
                raise RegulatoryTimelineUnavailableError(
                    "Regulatory timeline is temporarily unavailable. Please retry shortly."
                ) from exc
            schedule_regulatory_timeline_refresh()
            response = self._snapshot_to_response(snapshot, track=track, source_status="stale")
            self._record_served_snapshot(source_status=response.source_status, track=track)
            return response

        source_status: RegulatoryTimelineSourceStatus = "fresh"
        if self._is_snapshot_stale(snapshot):
            source_status = "stale"
            schedule_regulatory_timeline_refresh()

        response = self._snapshot_to_response(snapshot, track=track, source_status=source_status)
        self._record_served_snapshot(source_status=response.source_status, track=track)
        return response

    async def refresh_timeline(
        self,
        *,
        track: RegulatoryTimelineTrackFilter = "all",
        mode: str = "sync",
    ) -> RegulatoryTimelineResponse:
        """Fetch official sources, verify milestones, and persist a new snapshot."""
        refresh_started = perf_counter()
        refresh_result = "success"
        _refresh_attempts_total.labels(mode=mode, track=track).inc()
        try:
            seed_events = self._load_seed_events()

            timeout = httpx.Timeout(
                float(self.settings.regulatory_timeline_source_timeout_seconds),
                connect=min(10.0, float(self.settings.regulatory_timeline_source_timeout_seconds)),
            )

            async with _refresh_lock:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    verified_events = await self._build_verified_events(seed_events, client=client)

                fetched_at = datetime.now(UTC)
                expires_at = fetched_at + timedelta(
                    seconds=self.settings.regulatory_timeline_refresh_ttl_seconds
                )
                snapshot = await self._upsert_snapshot(
                    events_json={"events": verified_events},
                    digest_sha256=self._events_digest(verified_events),
                    fetched_at=fetched_at,
                    expires_at=expires_at,
                )

            return self._snapshot_to_response(snapshot, track=track, source_status="fresh")
        except RegulatoryTimelineValidationError:
            refresh_result = "validation_error"
            raise
        except Exception:
            refresh_result = "error"
            raise
        finally:
            _refresh_results_total.labels(mode=mode, track=track, result=refresh_result).inc()
            _refresh_duration_seconds.labels(
                mode=mode,
                track=track,
                result=refresh_result,
            ).observe(max(0.0, perf_counter() - refresh_started))

    async def _build_verified_events(
        self,
        seed_events: list[dict[str, Any]],
        *,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        verified_events: list[dict[str, Any]] = []
        verify_tasks = [self._verify_event(event, client=client) for event in seed_events]
        verify_results = await asyncio.gather(*verify_tasks, return_exceptions=True)

        for event, verify_result in zip(seed_events, verify_results, strict=False):
            if isinstance(verify_result, RegulatoryTimelineValidationError):
                raise verify_result

            if isinstance(verify_result, Exception):
                logger.warning(
                    "regulatory_timeline_event_verification_failed",
                    event_id=str(event.get("id", "unknown")),
                    error=str(verify_result),
                )
                continue

            verified_events.append(cast(dict[str, Any], verify_result))

        return verified_events

    async def _bootstrap_timeline_snapshot(self) -> RegulatoryTimelineSnapshot:
        """Insert a non-blocking seed-based snapshot while background verification runs."""
        seed_events = self._load_seed_events()
        fallback_events = self._build_bootstrap_events(seed_events)
        fetched_at = datetime.now(UTC)
        # Expire immediately so the first request schedules async refresh.
        expires_at = fetched_at
        return await self._upsert_snapshot(
            events_json={"events": fallback_events},
            digest_sha256=self._events_digest(fallback_events),
            fetched_at=fetched_at,
            expires_at=expires_at,
        )

    def _build_bootstrap_events(self, seed_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        checked_at = iso_now()
        bootstrap_events: list[dict[str, Any]] = []

        for raw_event in seed_events:
            track_raw = str(raw_event.get("track", "")).strip().lower()
            if track_raw not in {"regulation", "standards"}:
                raise RegulatoryTimelineValidationError(
                    "Event track must be regulation or standards"
                )

            date_precision_raw = str(raw_event.get("date_precision", "day")).strip().lower()
            if date_precision_raw not in {"day", "month"}:
                raise RegulatoryTimelineValidationError("date_precision must be day or month")

            event_id = str(raw_event.get("id", "")).strip()
            title = str(raw_event.get("title", "")).strip()
            date_value = str(raw_event.get("date", "")).strip()
            if not event_id or not title or not date_value:
                raise RegulatoryTimelineValidationError(
                    "Seed events require id, title, and date for bootstrap"
                )

            source_refs_raw = raw_event.get("source_refs")
            if not isinstance(source_refs_raw, list):
                source_refs_raw = []

            sources_payload: list[dict[str, Any]] = []
            for source_ref in source_refs_raw:
                if not isinstance(source_ref, dict):
                    continue

                sources_payload.append(
                    {
                        "label": str(source_ref.get("label", "")).strip() or "Official source",
                        "url": str(source_ref.get("url", "")).strip(),
                        "publisher": str(source_ref.get("publisher", "")).strip()
                        or "Official publisher",
                        "retrieved_at": checked_at,
                        "sha256": None,
                    }
                )

            bootstrap_events.append(
                {
                    "id": event_id,
                    "date": date_value,
                    "date_precision": date_precision_raw,
                    "track": cast(RegulatoryTimelineTrack, track_raw),
                    "title": title,
                    "plain_summary": str(raw_event.get("plain_summary", "")).strip() or title,
                    "audience_tags": self._coerce_string_list(raw_event.get("audience_tags")),
                    "verified": False,
                    "verification": {
                        "checked_at": checked_at,
                        "method": "manual",
                        "confidence": "low",
                    },
                    "sources": sources_payload,
                }
            )

        if not bootstrap_events:
            raise RegulatoryTimelineValidationError("Timeline seed file has no valid events")

        return bootstrap_events

    async def _verify_event(
        self,
        raw_event: dict[str, Any],
        *,
        client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        track_raw = str(raw_event.get("track", "")).strip().lower()
        if track_raw not in {"regulation", "standards"}:
            raise RegulatoryTimelineValidationError("Event track must be regulation or standards")
        track = cast(RegulatoryTimelineTrack, track_raw)

        date_precision_raw = str(raw_event.get("date_precision", "day")).strip().lower()
        if date_precision_raw not in {"day", "month"}:
            raise RegulatoryTimelineValidationError("date_precision must be day or month")

        date_value = str(raw_event.get("date", "")).strip()
        if not date_value:
            raise RegulatoryTimelineValidationError("date is required for timeline event")

        event_id = str(raw_event.get("id", "")).strip()
        if not event_id:
            raise RegulatoryTimelineValidationError("id is required for timeline event")

        title = str(raw_event.get("title", "")).strip()
        if not title:
            raise RegulatoryTimelineValidationError("title is required for timeline event")

        plain_summary = str(raw_event.get("plain_summary", "")).strip() or title
        audience_tags = self._coerce_string_list(raw_event.get("audience_tags"))
        expected_patterns = self._coerce_string_list(raw_event.get("expected_patterns"))

        source_refs_raw = raw_event.get("source_refs")
        if not isinstance(source_refs_raw, list) or not source_refs_raw:
            raise RegulatoryTimelineValidationError("source_refs must be a non-empty list")

        checked_at = iso_now()
        fetched_any = False
        matched_any = False
        sources_payload: list[dict[str, Any]] = []

        for source_ref in source_refs_raw:
            if not isinstance(source_ref, dict):
                continue

            label = str(source_ref.get("label", "")).strip() or "Official source"
            url = str(source_ref.get("url", "")).strip()
            publisher = str(source_ref.get("publisher", "")).strip() or "Official publisher"
            source_patterns = self._coerce_string_list(source_ref.get("expected_patterns"))
            effective_patterns = source_patterns if source_patterns else expected_patterns

            retrieved_at = checked_at
            sha256_hex: str | None = None
            matched = False

            try:
                self._assert_source_allowed(url=url, track=track)
                body_text, sha256_hex, retrieved_at = await self._fetch_source_text(
                    client,
                    url=url,
                    track=track,
                )
                fetched_any = True
                matched = self._match_patterns(body_text, effective_patterns)
                if matched:
                    matched_any = True
                    _source_fetch_results_total.labels(track=track, result="matched").inc()
                else:
                    _source_fetch_results_total.labels(track=track, result="mismatched").inc()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "regulatory_timeline_source_fetch_failed",
                    url=url,
                    track=track,
                    error=str(exc),
                )
                _source_fetch_results_total.labels(track=track, result="error").inc()

            sources_payload.append(
                {
                    "label": label,
                    "url": url,
                    "publisher": publisher,
                    "retrieved_at": retrieved_at,
                    "sha256": sha256_hex,
                }
            )

        method = "content-match" if matched_any else ("source-hash" if fetched_any else "manual")
        confidence = "high" if matched_any else ("medium" if fetched_any else "low")

        return {
            "id": event_id,
            "date": date_value,
            "date_precision": date_precision_raw,
            "track": track,
            "title": title,
            "plain_summary": plain_summary,
            "audience_tags": audience_tags,
            "verified": matched_any,
            "verification": {
                "checked_at": checked_at,
                "method": method,
                "confidence": confidence,
            },
            "sources": sources_payload,
        }

    async def _fetch_source_text(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        track: RegulatoryTimelineTrack,
    ) -> tuple[str, str, str]:
        current_url = url

        for _ in range(4):
            self._assert_source_allowed(url=current_url, track=track)
            response = await client.get(current_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise RegulatoryTimelineValidationError(
                        f"Redirect without location header: {current_url}"
                    )
                current_url = str(response.url.join(location))
                continue

            break
        else:
            raise RegulatoryTimelineValidationError(f"Too many redirects fetching {url}")

        response.raise_for_status()
        retrieved_at = iso_now()
        digest_sha256 = hashlib.sha256(response.content).hexdigest()
        return response.text, digest_sha256, retrieved_at

    @staticmethod
    def _events_digest(events: list[dict[str, Any]]) -> str:
        canonical_payload = json.dumps(
            {"events": events},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _record_served_snapshot(
        *,
        source_status: RegulatoryTimelineSourceStatus,
        track: RegulatoryTimelineTrackFilter,
    ) -> None:
        _served_snapshots_total.labels(source_status=source_status, track=track).inc()

    async def _upsert_snapshot(
        self,
        *,
        events_json: dict[str, Any],
        digest_sha256: str,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> RegulatoryTimelineSnapshot:
        snapshot = RegulatoryTimelineSnapshot(
            events_json=events_json,
            digest_sha256=digest_sha256,
            fetched_at=fetched_at,
            expires_at=expires_at,
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def _load_latest_snapshot(self) -> RegulatoryTimelineSnapshot | None:
        result = await self.db.execute(
            select(RegulatoryTimelineSnapshot)
            .order_by(desc(RegulatoryTimelineSnapshot.fetched_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _snapshot_to_response(
        self,
        snapshot: RegulatoryTimelineSnapshot,
        *,
        track: RegulatoryTimelineTrackFilter,
        source_status: RegulatoryTimelineSourceStatus,
    ) -> RegulatoryTimelineResponse:
        raw_events = (
            snapshot.events_json.get("events") if isinstance(snapshot.events_json, dict) else []
        )
        events = raw_events if isinstance(raw_events, list) else []

        filtered_events: list[dict[str, Any]] = []
        for raw_event in events:
            if not isinstance(raw_event, dict):
                continue

            event_track_raw = str(raw_event.get("track", "")).strip().lower()
            if track != "all" and event_track_raw != track:
                continue

            normalized = dict(raw_event)
            normalized["status"] = self._compute_status(
                date_value=str(normalized.get("date", "")),
                date_precision=str(normalized.get("date_precision", "day")),
            )

            if not self._is_verification_recent(normalized):
                normalized["verified"] = False
                verification = normalized.get("verification")
                if isinstance(verification, dict):
                    verification_payload = dict(verification)
                    verification_payload["confidence"] = "low"
                    normalized["verification"] = verification_payload

            filtered_events.append(normalized)

        filtered_events.sort(key=self._event_sort_key)

        validated_events = [
            RegulatoryTimelineEvent.model_validate(event) for event in filtered_events
        ]

        fetched_at = snapshot.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)

        return RegulatoryTimelineResponse(
            generated_at=iso_now(),
            fetched_at=fetched_at.astimezone(UTC).isoformat(),
            source_status=source_status,
            refresh_sla_seconds=self.settings.regulatory_timeline_refresh_ttl_seconds,
            digest_sha256=snapshot.digest_sha256,
            events=validated_events,
        )

    def _is_snapshot_stale(self, snapshot: RegulatoryTimelineSnapshot) -> bool:
        expires_at = snapshot.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expires_at.astimezone(UTC)

    def _is_verification_recent(self, event_payload: dict[str, Any]) -> bool:
        if not bool(event_payload.get("verified")):
            return False

        verification_raw = event_payload.get("verification")
        if not isinstance(verification_raw, dict):
            return False

        checked_at_raw = verification_raw.get("checked_at")
        if not isinstance(checked_at_raw, str) or not checked_at_raw.strip():
            return False

        try:
            checked_at = datetime.fromisoformat(checked_at_raw)
        except ValueError:
            return False

        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)

        max_age = timedelta(days=self.settings.regulatory_timeline_verify_max_age_days)
        return datetime.now(UTC) - checked_at.astimezone(UTC) <= max_age

    def _compute_status(
        self,
        *,
        date_value: str,
        date_precision: str,
    ) -> str:
        today = datetime.now(UTC).date()

        if date_precision == "month":
            try:
                event_year, event_month = self._parse_year_month(date_value)
            except ValueError:
                return "upcoming"

            today_year_month = (today.year, today.month)
            event_year_month = (event_year, event_month)
            if event_year_month < today_year_month:
                return "past"
            if event_year_month == today_year_month:
                return "today"
            return "upcoming"

        try:
            event_date = date.fromisoformat(date_value)
        except ValueError:
            return "upcoming"

        if event_date < today:
            return "past"
        if event_date == today:
            return "today"
        return "upcoming"

    def _event_sort_key(self, event_payload: dict[str, Any]) -> tuple[date, str]:
        date_value = str(event_payload.get("date", ""))
        date_precision = str(event_payload.get("date_precision", "day"))

        if date_precision == "month":
            try:
                year, month = self._parse_year_month(date_value)
                return date(year, month, 1), str(event_payload.get("id", ""))
            except ValueError:
                pass

        try:
            parsed = date.fromisoformat(date_value)
        except ValueError:
            parsed = date.max

        return parsed, str(event_payload.get("id", ""))

    def _load_seed_events(self) -> list[dict[str, Any]]:
        if not self._seed_path.exists():
            raise RegulatoryTimelineValidationError(
                f"Timeline seed file not found at {self._seed_path}"
            )

        try:
            payload = yaml.safe_load(self._seed_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RegulatoryTimelineValidationError("Timeline seed YAML is invalid") from exc

        if not isinstance(payload, dict):
            raise RegulatoryTimelineValidationError("Timeline seed file must contain an object")

        events_raw = payload.get("events")
        if not isinstance(events_raw, list):
            raise RegulatoryTimelineValidationError("Timeline seed file must include events list")

        events: list[dict[str, Any]] = []
        for item in events_raw:
            if isinstance(item, dict):
                events.append(item)

        if not events:
            raise RegulatoryTimelineValidationError("Timeline seed file has no valid events")

        return events

    def _assert_source_allowed(self, *, url: str, track: RegulatoryTimelineTrack) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if parsed.scheme not in {"https", "http"}:
            raise RegulatoryTimelineValidationError(f"Unsupported source URL scheme: {url}")

        allowed_hosts = (
            _REGULATION_ALLOWED_HOSTS if track == "regulation" else _STANDARDS_ALLOWED_HOSTS
        )
        if host not in allowed_hosts:
            raise RegulatoryTimelineValidationError(f"Source host is not allowlisted: {url}")

    def _match_patterns(self, source_text: str, patterns: list[str]) -> bool:
        if not patterns:
            return True

        text = source_text.lower()
        return any(pattern.lower() in text for pattern in patterns)

    @staticmethod
    def _coerce_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        items: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                normalized = entry.strip()
                if normalized:
                    items.append(normalized)
        return items

    @staticmethod
    def _parse_year_month(value: str) -> tuple[int, int]:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError("Expected YYYY-MM format")

        year = int(parts[0])
        month = int(parts[1])
        if month < 1 or month > 12:
            raise ValueError("Month out of range")

        return year, month


async def _refresh_in_background() -> None:
    try:
        async with get_background_session() as db:
            service = RegulatoryTimelineService(db)
            await service.refresh_timeline(track="all", mode="background")
            await db.commit()
    except RegulatoryTimelineValidationError as exc:
        logger.warning("regulatory_timeline_background_refresh_validation_failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.warning("regulatory_timeline_background_refresh_failed", error=str(exc))


def schedule_regulatory_timeline_refresh() -> None:
    """Schedule stale-source refresh if one is not already running."""
    global _refresh_task  # noqa: PLW0603

    loop = asyncio.get_running_loop()
    if _refresh_task and not _refresh_task.done():
        return

    _refresh_task = loop.create_task(_refresh_in_background())
