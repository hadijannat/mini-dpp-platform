"""E2E test: EDC dataspace connector health and publish flow.

Requires a running stack with EDC sidecar (--run-e2e or RUN_E2E=1).
These tests provision their own dataspace connector deterministically.
"""

from __future__ import annotations

import os
from uuid import UUID

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


def _create_dataspace_connector(api_client: httpx.Client, tenant_slug: str) -> str:
    """Provision a tenant-scoped dataspace EDC connector for test execution."""
    payload = {
        "name": "e2e-dataspace-edc",
        "runtime": "edc",
        "participant_id": os.getenv("E2E_EDC_PARTICIPANT_ID", "BPNL000000000000"),
        "runtime_config": {
            "management_url": os.getenv(
                "E2E_EDC_MANAGEMENT_URL",
                "http://edc-controlplane:19193/management",
            ),
            "dsp_endpoint": os.getenv(
                "E2E_EDC_DSP_ENDPOINT",
                "http://edc-controlplane:19194/protocol",
            ),
            "provider_connector_address": os.getenv(
                "E2E_PROVIDER_CONNECTOR_ADDRESS",
                "http://edc-controlplane:19193/management",
            ),
            "management_api_key_secret_ref": "edc-mgmt-api-key",
            "protocol": "dataspace-protocol-http",
        },
        "secrets": [
            {
                "secret_ref": "edc-mgmt-api-key",
                "value": os.getenv("E2E_EDC_API_KEY", "password"),
            }
        ],
    }
    create = api_client.post(
        f"/api/v1/tenants/{tenant_slug}/dataspace/connectors",
        json=payload,
    )
    assert create.status_code in (200, 201, 400), create.text

    if create.status_code == 400 and "already exists" in create.text.lower():
        connectors = api_client.get(f"/api/v1/tenants/{tenant_slug}/dataspace/connectors")
        assert connectors.status_code == 200, connectors.text
        for connector in connectors.json().get("connectors", []):
            if connector.get("name") == "e2e-dataspace-edc":
                connector_id = connector.get("id")
                assert connector_id, connectors.text
                return str(connector_id)
        raise AssertionError("Expected existing dataspace connector not found")

    assert create.status_code in (200, 201), create.text
    connector_id = create.json().get("id")
    assert connector_id, f"No connector id in response: {create.json()}"
    return str(connector_id)


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
def test_dataspace_connector_validate(runtime, api_client: httpx.Client) -> None:
    """Validate an EDC dataspace connector via v2 dataspace APIs."""
    connector_id = _create_dataspace_connector(api_client, runtime.tenant_slug)
    UUID(connector_id)

    validate = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/dataspace/connectors/{connector_id}/validate",
    )
    assert validate.status_code == 200, validate.text
    payload = validate.json()
    assert payload.get("status") in ("ok", "error")
    if payload.get("status") != "ok":
        pytest.fail(f"Connector validation failed: {payload}")


@pytest.mark.e2e
def test_dataspace_publish_flow(runtime, api_client: httpx.Client) -> None:
    """Publish a DPP through a deterministic dataspace connector flow."""
    connector_id = _create_dataspace_connector(api_client, runtime.tenant_slug)
    UUID(connector_id)

    dpp_id = _create_test_dpp(api_client, runtime.tenant_slug)
    UUID(dpp_id)

    publish = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/dataspace/assets/publish",
        json={
            "dpp_id": dpp_id,
            "connector_id": connector_id,
        },
    )
    assert publish.status_code == 200, publish.text
    result = publish.json()
    assert result.get("status") == "published"
    assert result.get("asset_id")

    assets = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/dataspace/connectors/{connector_id}/assets",
    )
    assert assets.status_code == 200, assets.text
    payload = assets.json()
    assert payload.get("count", 0) >= 1
    assert any(item.get("dpp_id") == dpp_id for item in payload.get("items", []))
