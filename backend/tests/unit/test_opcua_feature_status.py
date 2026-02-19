"""Tests for OPC UA feature status endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.tenancy import require_tenant_publisher
from app.main import create_application


def test_opcua_status_returns_disabled_when_feature_flag_off(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPCUA_ENABLED", "false")
    get_settings.cache_clear()
    try:
        app = create_application()
        app.dependency_overrides[require_tenant_publisher] = lambda: object()
        client = TestClient(app)
        response = client.get("/api/v1/tenants/default/opcua/status")
        assert response.status_code == 200
        assert response.json() == {"enabled": False}
    finally:
        get_settings.cache_clear()


def test_opcua_status_returns_enabled_when_feature_flag_on(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPCUA_ENABLED", "true")
    get_settings.cache_clear()
    try:
        app = create_application()
        app.dependency_overrides[require_tenant_publisher] = lambda: object()
        client = TestClient(app)
        response = client.get("/api/v1/tenants/default/opcua/status")
        assert response.status_code == 200
        assert response.json() == {"enabled": True}
    finally:
        get_settings.cache_clear()
