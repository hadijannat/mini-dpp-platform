"""OpenAPI contract checks for CEN facade route registration."""

from __future__ import annotations

from app.core.config import get_settings
from app.main import create_application


def test_cen_routes_not_mounted_when_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CEN_DPP_ENABLED", "false")
    get_settings.cache_clear()
    app = create_application()
    paths = set(app.openapi()["paths"].keys())
    assert "/api/v1/tenants/{tenant_slug}/cen/dpps" not in paths
    assert "/api/v1/public/{tenant_slug}/cen/dpps" not in paths
    get_settings.cache_clear()


def test_cen_operation_ids_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("CEN_DPP_ENABLED", "true")
    get_settings.cache_clear()
    app = create_application()
    openapi = app.openapi()
    operation_ids = {
        operation["operationId"]
        for methods in openapi["paths"].values()
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert {
        "CreateDPP",
        "ReadDPPById",
        "SearchDPPs",
        "ReadDPPByIdentifier",
        "UpdateDPP",
        "ArchiveDPP",
        "PublishDPP",
        "ValidateIdentifier",
        "SupersedeIdentifier",
        "SyncRegistryForDPP",
        "SyncResolverForDPP",
    }.issubset(operation_ids)
    get_settings.cache_clear()
