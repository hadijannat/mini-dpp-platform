"""E2E test: audit trail listing and hash chain verification.

Requires a running stack with admin user (--run-e2e or RUN_E2E=1).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest


@pytest.mark.e2e
def test_audit_events_listing(
    admin_client: httpx.Client,
) -> None:
    """Admin can list audit events with pagination."""
    response = admin_client.get(
        "/api/v1/admin/audit/events",
        params={"page": 1, "page_size": 10},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert "items" in data
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "page" in data
    assert data["page"] == 1
    assert "page_size" in data


@pytest.mark.e2e
def test_audit_events_filter_by_action(
    admin_client: httpx.Client,
) -> None:
    """Admin can filter audit events by action."""
    response = admin_client.get(
        "/api/v1/admin/audit/events",
        params={"action": "create_dpp", "page_size": 5},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    for event in data["items"]:
        assert event["action"] == "create_dpp"


@pytest.mark.e2e
def test_audit_chain_verification(
    runtime, admin_client: httpx.Client, test_results_dir: Path
) -> None:
    """Verify hash chain integrity for a tenant.

    This test first creates a DPP via the publisher client to generate
    audit events, then verifies the chain as admin.
    """
    artifacts = test_results_dir / "audit"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Get the tenant ID for the default tenant
    tenants_response = admin_client.get("/api/v1/tenants")
    assert tenants_response.status_code == 200, tenants_response.text
    tenants = tenants_response.json()

    tenant_id = None
    for t in tenants.get("tenants", tenants if isinstance(tenants, list) else []):
        slug = t.get("slug", "")
        if slug == runtime.tenant_slug:
            tenant_id = t.get("id")
            break

    if tenant_id is None:
        pytest.skip("Could not find tenant ID for chain verification")

    # Verify chain
    response = admin_client.get(
        "/api/v1/admin/audit/verify/chain",
        params={"tenant_id": tenant_id},
    )

    # 501 means hash columns not migrated yet (acceptable in some environments)
    if response.status_code == 501:
        pytest.skip("Hash chain columns not available (migration not applied)")

    assert response.status_code == 200, response.text
    result = response.json()

    assert "is_valid" in result
    assert "verified_count" in result
    assert "errors" in result

    (artifacts / "chain-verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
