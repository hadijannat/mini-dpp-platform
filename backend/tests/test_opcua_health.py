"""Tests for the agent health server."""

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app.opcua_agent.health import create_health_app


@pytest.mark.asyncio
async def test_healthz_returns_ok():
    app = create_health_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/healthz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_ok():
    app = create_health_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/readyz")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format():
    app = create_health_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/metrics")
        assert resp.status == 200
        text = await resp.text()
        assert "opcua_agent_connections_active" in text
