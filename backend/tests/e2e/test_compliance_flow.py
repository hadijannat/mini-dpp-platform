"""E2E test: compliance check flow against a live DPP.

Requires a running stack (--run-e2e or RUN_E2E=1).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest


def _extract_dpp_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("id", "dpp_id"):
            value = payload.get(key)
            if value:
                return str(value)
    raise AssertionError(f"Unable to extract DPP id from response: {payload}")


@pytest.mark.e2e
def test_compliance_check_on_dpp(
    runtime, api_client: httpx.Client, test_results_dir: Path
) -> None:
    """Create a DPP, then run a compliance check and verify the report shape."""
    artifacts = test_results_dir / "compliance"
    artifacts.mkdir(parents=True, exist_ok=True)

    # 1) Create a DPP with battery-related templates
    create_payload = {
        "asset_ids": {
            "manufacturerPartId": "COMPLIANCE-E2E-001",
            "serialNumber": "COMP-SN-001",
        },
        "selected_templates": ["digital-nameplate", "technical-data"],
    }
    create = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/dpps",
        json=create_payload,
    )
    assert create.status_code in (200, 201), create.text
    dpp_id = _extract_dpp_id(create.json())

    # 2) Run compliance check (auto-detect category)
    check = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/compliance/check/{dpp_id}",
    )
    assert check.status_code == 200, check.text
    report = check.json()

    # 3) Validate report structure
    assert "dpp_id" in report
    assert report["dpp_id"] == dpp_id
    assert "category" in report
    assert "is_compliant" in report
    assert isinstance(report["is_compliant"], bool)
    assert "checked_at" in report
    assert "violations" in report
    assert isinstance(report["violations"], list)
    assert "summary" in report

    summary = report["summary"]
    assert "total_rules" in summary
    assert "passed" in summary
    assert "critical_violations" in summary
    assert "warnings" in summary

    # 4) Save report
    (artifacts / f"{dpp_id}.compliance-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


@pytest.mark.e2e
def test_compliance_rules_listing(
    runtime, api_client: httpx.Client
) -> None:
    """Verify that rule categories are available."""
    response = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/compliance/rules",
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert "categories" in data
    assert isinstance(data["categories"], list)
    assert len(data["categories"]) >= 3  # battery, textile, electronic

    assert "rulesets" in data
    for cat in data["categories"]:
        assert cat in data["rulesets"]


@pytest.mark.e2e
def test_compliance_rules_for_category(
    runtime, api_client: httpx.Client
) -> None:
    """Verify category-specific rules can be fetched."""
    response = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/compliance/rules/battery",
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "rules" in data
    assert len(data["rules"]) > 0
