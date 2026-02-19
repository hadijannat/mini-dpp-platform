"""Health and metrics server for the OPC UA agent.

Exposes /healthz, /readyz, and /metrics on port 8090.
"""

from __future__ import annotations

import logging

from aiohttp import web
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger("opcua_agent.health")

REGISTRY = CollectorRegistry()

CONNECTIONS_ACTIVE = Gauge(
    "opcua_agent_connections_active",
    "Active OPC UA connections",
    registry=REGISTRY,
)
SUBSCRIPTIONS_ACTIVE = Gauge(
    "opcua_agent_subscriptions_active",
    "Active OPC UA subscriptions",
    registry=REGISTRY,
)
BUFFER_SIZE = Gauge(
    "opcua_agent_buffer_size",
    "Current ingestion buffer depth",
    registry=REGISTRY,
)
FLUSH_TOTAL = Counter(
    "opcua_agent_flush_total",
    "Total flush cycles completed",
    registry=REGISTRY,
)
FLUSH_DURATION = Histogram(
    "opcua_agent_flush_duration_seconds",
    "Flush cycle duration",
    registry=REGISTRY,
)
FLUSH_ERRORS = Counter(
    "opcua_agent_flush_errors_total",
    "Total flush errors",
    registry=REGISTRY,
)
DATA_CHANGES_TOTAL = Counter(
    "opcua_agent_data_changes_total",
    "Total data change notifications",
    registry=REGISTRY,
)
TRANSFORM_ERRORS = Counter(
    "opcua_agent_transform_errors_total",
    "Total transform failures",
    registry=REGISTRY,
)
DEAD_LETTERS_TOTAL = Counter(
    "opcua_agent_dead_letters_total",
    "Total dead letters",
    registry=REGISTRY,
)
RECONNECTS_TOTAL = Counter(
    "opcua_agent_reconnects_total",
    "Total reconnection attempts",
    registry=REGISTRY,
)


def create_health_app() -> web.Application:
    """Create the aiohttp application for health/metrics endpoints."""
    app = web.Application()
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/readyz", _readyz)
    app.router.add_get("/metrics", _metrics)
    return app


async def _healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _readyz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ready"})


async def _metrics(_request: web.Request) -> web.Response:
    body = generate_latest(REGISTRY)
    return web.Response(body=body, content_type="text/plain; version=0.0.4")
