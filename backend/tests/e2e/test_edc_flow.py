"""E2E test: EDC dataspace connector health and publish flow.

Requires a running stack with EDC sidecar (--run-e2e or RUN_E2E=1).
These tests gracefully skip when EDC is not configured.
"""

from __future__ import annotations

import httpx
import pytest


def _create_test_dpp(api_client: httpx.Client, tenant_slug: str) -> str:
    """Create a DPP and publish it (EDC requires published DPPs)."""
    create_payload = {
        "asset_ids": {
            "manufacturerPartId": "EDC-E2E-001",
            "serialNumber": "EDC-SN-001",
        },
        "selected_templates": ["digital-nameplate"],
    }
    create = api_client.post(
        f"/api/v1/tenants/{tenant_slug}/dpps",
        json=create_payload,
    )
    assert create.status_code in (200, 201), create.text
    dpp_id = create.json().get("id", create.json().get("dpp_id", ""))
    assert dpp_id, f"No DPP id in response: {create.json()}"

    # Publish the DPP
    publish = api_client.post(
        f"/api/v1/tenants/{tenant_slug}/dpps/{dpp_id}/publish",
    )
    assert publish.status_code in (200, 400), publish.text

    return str(dpp_id)


@pytest.mark.e2e
def test_health_endpoint_includes_edc(runtime) -> None:
    """The /health endpoint reports EDC status when configured."""
    response = httpx.get(f"{runtime.dpp_base_url}/health", timeout=10.0)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "checks" in data
    # EDC might not be configured, but the health endpoint should work
    # regardless. If EDC is configured, it should appear in checks.
    if "edc" in data["checks"]:
        assert data["checks"]["edc"] in ("ok", "unavailable")


@pytest.mark.e2e
def test_edc_connector_health(runtime, api_client: httpx.Client) -> None:
    """Check EDC health through a connector, skipping if no connectors exist."""
    # List connectors
    response = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/connectors",
    )
    assert response.status_code == 200, response.text
    connectors = response.json().get("connectors", [])

    # Find an EDC-type connector
    edc_connector = None
    for c in connectors:
        if c.get("connector_type") == "edc":
            edc_connector = c
            break

    if edc_connector is None:
        pytest.skip("No EDC connector configured — skipping EDC health check")

    # Check EDC health through the connector
    health = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/connectors/{edc_connector['id']}/dataspace/health",
    )
    assert health.status_code == 200, health.text
    data = health.json()
    assert "status" in data


@pytest.mark.e2e
def test_edc_publish_flow(runtime, api_client: httpx.Client) -> None:
    """Publish a DPP to EDC dataspace, skipping if no EDC connectors."""
    # List connectors to find an EDC one
    response = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/connectors",
    )
    assert response.status_code == 200, response.text
    connectors = response.json().get("connectors", [])

    edc_connector = None
    for c in connectors:
        if c.get("connector_type") == "edc":
            edc_connector = c
            break

    if edc_connector is None:
        pytest.skip("No EDC connector configured — skipping EDC publish flow")

    # Create and publish a DPP
    dpp_id = _create_test_dpp(api_client, runtime.tenant_slug)

    # Publish to EDC dataspace
    publish = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/connectors/"
        f"{edc_connector['id']}/dataspace/publish/{dpp_id}",
    )
    assert publish.status_code == 200, publish.text
    result = publish.json()
    assert "status" in result

    # Check dataspace status
    status = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/connectors/"
        f"{edc_connector['id']}/dataspace/status/{dpp_id}",
    )
    assert status.status_code == 200, status.text
    status_data = status.json()
    assert "registered" in status_data
