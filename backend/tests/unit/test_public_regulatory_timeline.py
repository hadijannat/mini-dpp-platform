"""Unit tests for public verified regulatory timeline endpoint and service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import app.modules.regulatory_timeline.service as regulatory_timeline_service_module
from app.db.models import RegulatoryTimelineSnapshot
from app.db.session import get_db_session
from app.modules.regulatory_timeline.public_router import router
from app.modules.regulatory_timeline.schemas import RegulatoryTimelineResponse
from app.modules.regulatory_timeline.service import (
    RegulatoryTimelineService,
    RegulatoryTimelineValidationError,
)


@dataclass
class _FakeScalarResult:
    row: Any

    def scalar_one_or_none(self) -> Any:
        return self.row


class _FakeSession:
    def __init__(self, snapshots: list[RegulatoryTimelineSnapshot] | None = None) -> None:
        self.snapshots = snapshots or []

    async def execute(self, statement: object) -> _FakeScalarResult:
        sql = str(statement)
        if "FROM regulatory_timeline_snapshots" not in sql:
            return _FakeScalarResult(None)

        if not self.snapshots:
            return _FakeScalarResult(None)

        latest = max(self.snapshots, key=lambda item: item.fetched_at)
        return _FakeScalarResult(latest)

    def add(self, snapshot: RegulatoryTimelineSnapshot) -> None:
        self.snapshots.append(snapshot)

    async def flush(self) -> None:
        return None


@pytest.fixture()
def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/public")
    return app


def _snapshot(*, stale: bool = False) -> RegulatoryTimelineSnapshot:
    now = datetime.now(UTC)
    return RegulatoryTimelineSnapshot(
        events_json={
            "events": [
                {
                    "id": "espr-entry-into-force",
                    "date": "2024-07-18",
                    "date_precision": "day",
                    "track": "regulation",
                    "title": "ESPR entered into force",
                    "plain_summary": "Summary",
                    "audience_tags": ["brands"],
                    "verified": True,
                    "verification": {
                        "checked_at": now.isoformat(),
                        "method": "content-match",
                        "confidence": "high",
                    },
                    "sources": [
                        {
                            "label": "Commission",
                            "url": "https://commission.europa.eu/example",
                            "publisher": "European Commission",
                            "retrieved_at": now.isoformat(),
                            "sha256": "a" * 64,
                        }
                    ],
                },
                {
                    "id": "cencenelec-jtc24-established",
                    "date": "2023-09",
                    "date_precision": "month",
                    "track": "standards",
                    "title": "JTC24 established",
                    "plain_summary": "Summary",
                    "audience_tags": ["standards"],
                    "verified": True,
                    "verification": {
                        "checked_at": now.isoformat(),
                        "method": "content-match",
                        "confidence": "high",
                    },
                    "sources": [
                        {
                            "label": "CEN-CENELEC",
                            "url": "https://www.cencenelec.eu/example",
                            "publisher": "CEN-CENELEC",
                            "retrieved_at": now.isoformat(),
                            "sha256": "b" * 64,
                        }
                    ],
                },
            ]
        },
        digest_sha256="c" * 64,
        fetched_at=now,
        expires_at=now - timedelta(hours=1) if stale else now + timedelta(hours=4),
    )


@pytest.mark.asyncio
async def test_service_track_filter_and_month_precision_status() -> None:
    fake_db = _FakeSession([_snapshot(stale=False)])
    service = RegulatoryTimelineService(fake_db)  # type: ignore[arg-type]

    standards_only = await service.get_latest_timeline(track="standards")

    assert standards_only.source_status == "fresh"
    assert len(standards_only.events) == 1
    assert standards_only.events[0].track == "standards"
    assert standards_only.events[0].date_precision == "month"


@pytest.mark.asyncio
async def test_service_allowlist_rejects_non_official_host() -> None:
    service = RegulatoryTimelineService(_FakeSession())  # type: ignore[arg-type]

    with pytest.raises(RegulatoryTimelineValidationError):
        service._assert_source_allowed(url="https://example.com/not-allowed", track="regulation")


@pytest.mark.asyncio
async def test_stale_snapshot_schedules_single_refresh() -> None:
    fake_db = _FakeSession([_snapshot(stale=True)])
    service = RegulatoryTimelineService(fake_db)  # type: ignore[arg-type]

    counter = {"runs": 0}

    async def fake_background_refresh() -> None:
        counter["runs"] += 1
        await asyncio.sleep(0.05)

    regulatory_timeline_service_module._refresh_task = None
    original_refresh = regulatory_timeline_service_module._refresh_in_background
    regulatory_timeline_service_module._refresh_in_background = fake_background_refresh

    try:
        first, second = await asyncio.gather(
            service.get_latest_timeline(track="all"),
            service.get_latest_timeline(track="all"),
        )
        assert first.source_status == "stale"
        assert second.source_status == "stale"

        await asyncio.sleep(0.08)
        assert counter["runs"] == 1
    finally:
        regulatory_timeline_service_module._refresh_in_background = original_refresh
        task = regulatory_timeline_service_module._refresh_task
        if task is not None and not task.done():
            await task
        regulatory_timeline_service_module._refresh_task = None


@pytest.mark.asyncio
async def test_initial_bootstrap_returns_stale_and_schedules_refresh() -> None:
    fake_db = _FakeSession([])
    service = RegulatoryTimelineService(fake_db)  # type: ignore[arg-type]

    counter = {"runs": 0}

    async def fake_background_refresh() -> None:
        counter["runs"] += 1
        await asyncio.sleep(0.05)

    regulatory_timeline_service_module._refresh_task = None
    original_refresh = regulatory_timeline_service_module._refresh_in_background
    regulatory_timeline_service_module._refresh_in_background = fake_background_refresh

    try:
        response = await service.get_latest_timeline(track="all")
        assert response.source_status == "stale"
        assert len(response.events) > 0
        assert len(fake_db.snapshots) == 1

        await asyncio.sleep(0.08)
        assert counter["runs"] == 1
    finally:
        regulatory_timeline_service_module._refresh_in_background = original_refresh
        task = regulatory_timeline_service_module._refresh_task
        if task is not None and not task.done():
            await task
        regulatory_timeline_service_module._refresh_task = None


@pytest.mark.asyncio
async def test_verify_event_sets_content_match_and_source_hash_confidence() -> None:
    service = RegulatoryTimelineService(_FakeSession())  # type: ignore[arg-type]

    event = {
        "id": "espr-entry-into-force",
        "date": "2024-07-18",
        "date_precision": "day",
        "track": "regulation",
        "title": "ESPR entered into force",
        "plain_summary": "Summary",
        "audience_tags": ["brands"],
        "expected_patterns": ["entered into force"],
        "source_refs": [
            {
                "label": "Commission",
                "url": "https://commission.europa.eu/example",
                "publisher": "European Commission",
            }
        ],
    }

    checked_at = datetime.now(UTC).isoformat()
    service._fetch_source_text = AsyncMock(  # type: ignore[method-assign]
        return_value=("Regulation entered into force on 18 July 2024", "a" * 64, checked_at)
    )
    matched = await service._verify_event(event, client=AsyncMock())  # type: ignore[arg-type]
    assert matched["verified"] is True
    assert matched["verification"]["method"] == "content-match"
    assert matched["verification"]["confidence"] == "high"

    service._fetch_source_text = AsyncMock(  # type: ignore[method-assign]
        return_value=("No expected phrase here", "b" * 64, checked_at)
    )
    unmatched = await service._verify_event(event, client=AsyncMock())  # type: ignore[arg-type]
    assert unmatched["verified"] is False
    assert unmatched["verification"]["method"] == "source-hash"
    assert unmatched["verification"]["confidence"] == "medium"


@pytest.mark.asyncio
async def test_stale_verification_downgrades_verified_badge() -> None:
    snapshot = _snapshot(stale=False)
    old_checked_at = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    events = snapshot.events_json.get("events")
    assert isinstance(events, list)
    first_event = events[0]
    assert isinstance(first_event, dict)
    verification = first_event.get("verification")
    assert isinstance(verification, dict)
    verification["checked_at"] = old_checked_at

    fake_db = _FakeSession([snapshot])
    service = RegulatoryTimelineService(fake_db)  # type: ignore[arg-type]
    response = await service.get_latest_timeline(track="regulation")
    assert len(response.events) == 1
    assert response.events[0].verified is False
    assert response.events[0].verification.confidence == "low"


@pytest.mark.asyncio
async def test_public_route_sets_cache_etag_and_server_timing(_app: FastAPI) -> None:
    payload = RegulatoryTimelineResponse(
        generated_at="2026-02-14T00:00:00+00:00",
        fetched_at="2026-02-14T00:00:00+00:00",
        source_status="fresh",
        refresh_sla_seconds=82800,
        digest_sha256="d" * 64,
        events=[],
    )

    service_mock = AsyncMock(return_value=payload)

    async def _override_db() -> Any:
        return object()

    _app.dependency_overrides[get_db_session] = _override_db

    from app.modules.regulatory_timeline import public_router as public_router_module

    original_get_latest = public_router_module.RegulatoryTimelineService.get_latest_timeline
    public_router_module.RegulatoryTimelineService.get_latest_timeline = service_mock

    try:
        transport = ASGITransport(app=_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/public/landing/regulatory-timeline")

        assert response.status_code == 200
        assert (
            response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=3600"
        )
        assert response.headers["etag"] == f'"{"d" * 64}"'
        assert "regulatory_timeline;dur=" in response.headers["server-timing"]
        body = response.json()
        assert set(body.keys()) == {
            "generated_at",
            "fetched_at",
            "source_status",
            "refresh_sla_seconds",
            "digest_sha256",
            "events",
        }
        blocked = {
            "dpp_id",
            "serialNumber",
            "batchId",
            "globalAssetId",
            "payload",
            "owner_subject",
            "user_subject",
            "email",
        }
        assert not (set(body.keys()) & blocked)
    finally:
        public_router_module.RegulatoryTimelineService.get_latest_timeline = original_get_latest
        _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_route_returns_304_on_if_none_match(_app: FastAPI) -> None:
    payload = RegulatoryTimelineResponse(
        generated_at="2026-02-14T00:00:00+00:00",
        fetched_at="2026-02-14T00:00:00+00:00",
        source_status="stale",
        refresh_sla_seconds=82800,
        digest_sha256="e" * 64,
        events=[],
    )

    service_mock = AsyncMock(return_value=payload)

    async def _override_db() -> Any:
        return object()

    _app.dependency_overrides[get_db_session] = _override_db

    from app.modules.regulatory_timeline import public_router as public_router_module

    original_get_latest = public_router_module.RegulatoryTimelineService.get_latest_timeline
    public_router_module.RegulatoryTimelineService.get_latest_timeline = service_mock

    try:
        transport = ASGITransport(app=_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/public/landing/regulatory-timeline",
                headers={"If-None-Match": f'"{"e" * 64}"'},
            )

        assert response.status_code == 304
        assert (
            response.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=3600"
        )
        assert response.headers["etag"] == f'"{"e" * 64}"'
        assert "regulatory_timeline;dur=" in response.headers["server-timing"]
    finally:
        public_router_module.RegulatoryTimelineService.get_latest_timeline = original_get_latest
        _app.dependency_overrides.clear()
