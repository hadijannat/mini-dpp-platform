"""Unit tests for public landing summary metrics endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db.models import TenantStatus
from app.db.session import get_db_session
from app.modules.dpps.public_router import PublicLandingSummaryResponse, router


@pytest.fixture()
def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/public")
    return app


class _FakeScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value

    def scalar_one(self) -> object:
        return self._value


class _FakeSession:
    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self._call_idx = 0
        self.statements: list[object] = []

    async def execute(self, _stmt: object) -> object:
        self.statements.append(_stmt)
        idx = self._call_idx
        self._call_idx += 1
        if idx < len(self._results):
            return self._results[idx]
        return _FakeScalarResult(None)


def _make_tenant() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        slug="default",
        name="Default",
        status=TenantStatus.ACTIVE,
    )


def test_summary_schema_is_aggregate_only() -> None:
    fields = set(PublicLandingSummaryResponse.model_fields.keys())
    assert fields == {
        "tenant_slug",
        "published_dpps",
        "active_product_families",
        "dpps_with_traceability",
        "latest_publish_at",
        "generated_at",
        "scope",
        "refresh_sla_seconds",
    }


@pytest.mark.asyncio
async def test_public_landing_summary_success(_app: FastAPI) -> None:
    tenant = _make_tenant()
    latest_publish = datetime(2026, 2, 9, 12, 0, tzinfo=UTC)
    fake_session = _FakeSession(
        [
            _FakeScalarResult(tenant),  # _resolve_tenant
            _FakeScalarResult(12),  # published_dpps
            _FakeScalarResult(4),  # active_product_families
            _FakeScalarResult(7),  # dpps_with_traceability
            _FakeScalarResult(latest_publish),  # latest_publish_at
        ]
    )

    async def _override_db() -> Any:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public/default/landing/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=15, stale-while-revalidate=15"
    assert "server-timing" in response.headers
    assert "landing_summary;dur=" in response.headers["server-timing"]
    assert "x-landing-freshness-age-seconds" in response.headers
    body = response.json()
    assert body["tenant_slug"] == "default"
    assert body["published_dpps"] == 12
    assert body["active_product_families"] == 4
    assert body["dpps_with_traceability"] == 7
    assert body["latest_publish_at"] == latest_publish.isoformat()
    assert "generated_at" in body
    datetime.fromisoformat(body["generated_at"])
    assert body["scope"] == "default"
    assert body["refresh_sla_seconds"] == 30

    blocked = {
        "dpp_id",
        "aas_id",
        "asset_ids",
        "serialNumber",
        "batchId",
        "globalAssetId",
        "payload",
        "read_point",
        "biz_location",
        "owner_subject",
        "user_subject",
        "email",
    }
    assert not (set(body.keys()) & blocked)
    sql_fragments = [str(stmt) for stmt in fake_session.statements[1:]]
    assert all("dpps.status = :status_1" in sql for sql in sql_fragments[:3])

    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_landing_summary_unknown_tenant_returns_404(_app: FastAPI) -> None:
    fake_session = _FakeSession([_FakeScalarResult(None)])

    async def _override_db() -> Any:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public/unknown/landing/summary")

    assert response.status_code == 404
    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_landing_summary_returns_zeroed_aggregates_when_no_data(_app: FastAPI) -> None:
    tenant = _make_tenant()
    fake_session = _FakeSession(
        [
            _FakeScalarResult(tenant),  # _resolve_tenant
            _FakeScalarResult(None),  # published_dpps
            _FakeScalarResult(None),  # active_product_families
            _FakeScalarResult(None),  # dpps_with_traceability
            _FakeScalarResult(None),  # latest_publish_at
        ]
    )

    async def _override_db() -> Any:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public/default/landing/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["published_dpps"] == 0
    assert body["active_product_families"] == 0
    assert body["dpps_with_traceability"] == 0
    assert body["latest_publish_at"] is None
    assert body["scope"] == "default"
    assert body["refresh_sla_seconds"] == 30
    assert "x-landing-freshness-age-seconds" not in response.headers
    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_scoped_landing_summary_default_scope(_app: FastAPI) -> None:
    tenant = _make_tenant()
    latest_publish = datetime(2026, 2, 9, 12, 0, tzinfo=UTC)
    fake_session = _FakeSession(
        [
            _FakeScalarResult(tenant),  # _resolve_tenant
            _FakeScalarResult(3),  # published_dpps
            _FakeScalarResult(2),  # active_product_families
            _FakeScalarResult(1),  # dpps_with_traceability
            _FakeScalarResult(latest_publish),  # latest_publish_at
        ]
    )

    async def _override_db() -> Any:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public/landing/summary?scope=default")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=15, stale-while-revalidate=15"
    assert "server-timing" in response.headers
    assert "x-landing-freshness-age-seconds" in response.headers
    body = response.json()
    assert body["tenant_slug"] == "default"
    assert body["scope"] == "default"
    assert body["published_dpps"] == 3
    assert body["active_product_families"] == 2
    assert body["dpps_with_traceability"] == 1
    assert body["latest_publish_at"] == latest_publish.isoformat()
    assert body["refresh_sla_seconds"] == 30
    _app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_scoped_landing_summary_all_scope(_app: FastAPI) -> None:
    latest_publish = datetime(2026, 2, 9, 12, 0, tzinfo=UTC)
    fake_session = _FakeSession(
        [
            _FakeScalarResult(21),  # published_dpps
            _FakeScalarResult(11),  # active_product_families
            _FakeScalarResult(8),  # dpps_with_traceability
            _FakeScalarResult(latest_publish),  # latest_publish_at
        ]
    )

    async def _override_db() -> Any:
        return fake_session

    _app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/public/landing/summary")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=15, stale-while-revalidate=15"
    assert "server-timing" in response.headers
    assert "x-landing-freshness-age-seconds" in response.headers
    body = response.json()
    assert body["tenant_slug"] == "all"
    assert body["scope"] == "all"
    assert body["published_dpps"] == 21
    assert body["active_product_families"] == 11
    assert body["dpps_with_traceability"] == 8
    assert body["latest_publish_at"] == latest_publish.isoformat()
    assert body["refresh_sla_seconds"] == 30
    _app.dependency_overrides.clear()
