"""Unit tests for CIRPASS story feed parser and stale refresh behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest

import app.modules.cirpass.service as cirpass_service_module
from app.db.models import CirpassStorySnapshot
from app.modules.cirpass.parser import CirpassSourceParser
from app.modules.cirpass.service import (
    CirpassLabService,
    CirpassParseError,
    CirpassUnavailableError,
)


@dataclass
class _FakeScalarResult:
    rows: list[Any]

    def scalar_one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None


class _FakeSession:
    def __init__(self, snapshots: list[CirpassStorySnapshot] | None = None) -> None:
        self.snapshots = snapshots or []

    async def execute(self, statement: object) -> _FakeScalarResult:
        sql = str(statement)
        params = statement.compile().params  # type: ignore[attr-defined]

        if "FROM cirpass_story_snapshots" not in sql:
            return _FakeScalarResult([])

        if "ORDER BY cirpass_story_snapshots.fetched_at DESC" in sql:
            if not self.snapshots:
                return _FakeScalarResult([])
            latest = max(self.snapshots, key=lambda item: item.fetched_at)
            return _FakeScalarResult([latest])

        version = params.get("version_1")
        record_url = params.get("zenodo_record_url_1")
        for snapshot in self.snapshots:
            if snapshot.version == version and snapshot.zenodo_record_url == record_url:
                return _FakeScalarResult([snapshot])
        return _FakeScalarResult([])

    def add(self, snapshot: CirpassStorySnapshot) -> None:
        self.snapshots.append(snapshot)

    async def flush(self) -> None:  # pragma: no cover - no-op for fake session
        return None


@pytest.mark.asyncio
async def test_parser_extracts_version_date_and_official_links() -> None:
    parser = CirpassSourceParser("https://cirpassproject.eu/project-results/")

    async def _mock_download_pdf_text(_client: httpx.AsyncClient, _pdf_url: str) -> str:
        return (
            "CIRPASS User Stories V3.1. User Story 1: Create a DPP payload. "
            "User Story 2: Access restricted views. User Story 3: Update repair event."
        )

    parser._download_pdf_text = _mock_download_pdf_text  # type: ignore[method-assign]

    html = """
        <html>
          <body>
            <a href=\"https://zenodo.org/records/17979585\">CIRPASS User Stories V3.1</a>
          </body>
        </html>
    """

    zenodo_json = {
        "metadata": {
            "title": "CIRPASS User Stories V3.1",
            "publication_date": "2025-12-19",
        },
        "files": [
            {
                "key": "cirpass_user_stories_v3_1.pdf",
                "links": {
                    "self": "https://zenodo.org/api/records/17979585/files/story.pdf/content"
                },
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://cirpassproject.eu/project-results/":
            return httpx.Response(200, text=html)
        if str(request.url) == "https://zenodo.org/api/records/17979585":
            return httpx.Response(200, json=zenodo_json)
        if str(request.url).startswith("https://zenodo.org/api/records/17979585/files/"):
            return httpx.Response(200, content=b"%PDF-1.4")
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        feed = await parser.fetch_latest_feed(client)

    assert feed.version == "V3.1"
    assert feed.release_date == "2025-12-19"
    assert feed.zenodo_record_url == "https://zenodo.org/records/17979585"
    assert len(feed.levels) == 5


@pytest.mark.asyncio
async def test_stale_snapshot_returns_stale_and_schedules_single_refresh() -> None:
    stale_snapshot = CirpassStorySnapshot(
        version="V3.1",
        release_date=date(2025, 12, 19),
        source_url="https://cirpassproject.eu/project-results/",
        zenodo_record_url="https://zenodo.org/records/17979585",
        zenodo_record_id="17979585",
        stories_json={
            "levels": [
                {
                    "level": "create",
                    "label": "CREATE",
                    "objective": "Create",
                    "stories": [{"id": "1", "title": "Create", "summary": "summary"}],
                },
                {
                    "level": "access",
                    "label": "ACCESS",
                    "objective": "Access",
                    "stories": [{"id": "2", "title": "Access", "summary": "summary"}],
                },
                {
                    "level": "update",
                    "label": "UPDATE",
                    "objective": "Update",
                    "stories": [{"id": "3", "title": "Update", "summary": "summary"}],
                },
                {
                    "level": "transfer",
                    "label": "TRANSFER",
                    "objective": "Transfer",
                    "stories": [{"id": "4", "title": "Transfer", "summary": "summary"}],
                },
                {
                    "level": "deactivate",
                    "label": "DEACTIVATE",
                    "objective": "Deactivate",
                    "stories": [{"id": "5", "title": "Deactivate", "summary": "summary"}],
                },
            ]
        },
        fetched_at=datetime.now(UTC) - timedelta(hours=24),
    )

    fake_db = _FakeSession([stale_snapshot])

    counter = {"runs": 0}

    async def fake_background_refresh() -> None:
        counter["runs"] += 1
        await asyncio.sleep(0.05)

    cirpass_service_module._refresh_task = None
    original_refresh = cirpass_service_module._refresh_in_background
    cirpass_service_module._refresh_in_background = fake_background_refresh

    try:
        service = CirpassLabService(fake_db)  # type: ignore[arg-type]
        first, second = await asyncio.gather(
            service.get_latest_stories(), service.get_latest_stories()
        )
        assert first.source_status == "stale"
        assert second.source_status == "stale"

        await asyncio.sleep(0.08)
        assert counter["runs"] == 1
    finally:
        cirpass_service_module._refresh_in_background = original_refresh
        task = cirpass_service_module._refresh_task
        if task is not None and not task.done():
            await task
        cirpass_service_module._refresh_task = None


@pytest.mark.asyncio
async def test_no_snapshot_and_refresh_failure_raises_unavailable() -> None:
    service = CirpassLabService(_FakeSession())  # type: ignore[arg-type]

    async def failing_refresh() -> object:
        raise CirpassParseError("source unavailable")

    service.refresh_stories = failing_refresh  # type: ignore[method-assign]

    with pytest.raises(CirpassUnavailableError):
        await service.get_latest_stories()
