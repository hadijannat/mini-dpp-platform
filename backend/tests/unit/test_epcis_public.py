"""Unit tests for the public EPCIS endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.db.models import DPPStatus, EPCISEventType, TenantStatus
from app.db.session import get_db_session
from app.modules.epcis.public_router import router

# ---------------------------------------------------------------------------
# Minimal test app
# ---------------------------------------------------------------------------


@pytest.fixture()
def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/public")
    return app


# ---------------------------------------------------------------------------
# Fake DB session that returns pre-configured results per query
# ---------------------------------------------------------------------------


class _FakeScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _FakeScalarsResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> _FakeScalarsResult:
        return self

    def all(self) -> list[object]:
        return self._values


class _FakeSession:
    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self._call_idx = 0

    async def execute(self, _stmt: object) -> object:
        idx = self._call_idx
        self._call_idx += 1
        if idx < len(self._results):
            return self._results[idx]
        return _FakeScalarResult(None)


# ---------------------------------------------------------------------------
# SimpleNamespace-based mock objects (avoids SQLAlchemy ORM state issues)
# ---------------------------------------------------------------------------

_TENANT_ID = uuid4()


def _make_tenant() -> SimpleNamespace:
    return SimpleNamespace(
        id=_TENANT_ID,
        slug="default",
        name="Default",
        status=TenantStatus.ACTIVE,
    )


def _make_dpp(*, published: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=_TENANT_ID,
        status=DPPStatus.PUBLISHED if published else DPPStatus.DRAFT,
    )


def _make_epcis_event(dpp_id: object) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=_TENANT_ID,
        dpp_id=dpp_id,
        event_id=f"urn:uuid:{uuid4()}",
        event_type=EPCISEventType.OBJECT,
        event_time=datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC),
        event_time_zone_offset="+01:00",
        action="OBSERVE",
        biz_step="shipping",
        disposition="in_transit",
        read_point=None,
        biz_location=None,
        payload={},
        error_declaration=None,
        created_by_subject="test-user",
        created_at=datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_published_dpp_returns_events(_app: FastAPI) -> None:
    """Published DPP should return its EPCIS events."""
    tenant = _make_tenant()
    dpp = _make_dpp(published=True)
    event = _make_epcis_event(dpp.id)

    fake_session = _FakeSession([
        _FakeScalarResult(tenant),
        _FakeScalarResult(dpp),
        _FakeScalarsResult([event]),
    ])

    async def _override_db() -> object:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/public/default/epcis/events/{dpp.id}")

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["type"] == "EPCISQueryDocument"
    assert len(body["eventList"]) == 1
    assert body["eventList"][0]["event_id"] == event.event_id

    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_draft_dpp_returns_404(_app: FastAPI) -> None:
    """Draft DPP should return 404 — events only visible on published DPPs."""
    tenant = _make_tenant()
    dpp_id = uuid4()

    fake_session = _FakeSession([
        _FakeScalarResult(tenant),
        _FakeScalarResult(None),  # published filter excludes drafts
    ])

    async def _override_db() -> object:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/public/default/epcis/events/{dpp_id}")

    assert resp.status_code == status.HTTP_404_NOT_FOUND

    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nonexistent_dpp_returns_404(_app: FastAPI) -> None:
    """Non-existent DPP should return 404."""
    tenant = _make_tenant()
    dpp_id = uuid4()

    fake_session = _FakeSession([
        _FakeScalarResult(tenant),
        _FakeScalarResult(None),
    ])

    async def _override_db() -> object:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/public/default/epcis/events/{dpp_id}")

    assert resp.status_code == status.HTTP_404_NOT_FOUND

    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nonexistent_tenant_returns_404(_app: FastAPI) -> None:
    """Non-existent tenant slug should return 404."""
    fake_session = _FakeSession([
        _FakeScalarResult(None),
    ])

    async def _override_db() -> object:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db

    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/public/no-such-tenant/epcis/events/{uuid4()}")

    assert resp.status_code == status.HTTP_404_NOT_FOUND

    _app.dependency_overrides.clear()
