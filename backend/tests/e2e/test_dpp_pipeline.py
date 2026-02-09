from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest


def _extract_dpp_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("id", "dpp_id", "dppId", "uuid"):
            value = payload.get(key)
            if value:
                return str(value)
    raise AssertionError(f"Unable to extract DPP id from response: {payload}")


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _resolve_compliance_cmd() -> list[str] | None:
    env_cmd = os.getenv("COMPLIANCE_TOOL_CMD")
    if env_cmd:
        return shlex.split(env_cmd)

    exe = shutil.which("aas-compliance-check")
    if exe:
        return [exe]

    if importlib.util.find_spec("aas_compliance_tool"):
        python = shutil.which("python") or "python"
        return [python, "-m", "aas_compliance_tool.cli"]

    return None


def _run_compliance_tool(cmd: list[str], file_path: Path, *, is_aasx: bool) -> tuple[bool, str]:
    args = ["deserialization", "--json"]
    if is_aasx:
        args.append("--aasx")

    full = cmd + args + [str(file_path)]
    proc = subprocess.run(full, capture_output=True, text=True)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return proc.returncode == 0, output


@pytest.mark.e2e
def test_pipeline_refresh_build_export(
    runtime, api_client: httpx.Client, test_results_dir: Path
) -> None:
    artifacts = test_results_dir / "pipeline"
    artifacts.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {"steps": {}, "artifacts": {}}

    # 1) Refresh templates (IDTA)
    refresh = api_client.post("/api/v1/templates/refresh")
    assert refresh.status_code in (200, 201), refresh.text
    refresh_payload = refresh.json()
    report["steps"]["refresh"] = {
        "status_code": refresh.status_code,
        "attempted_count": refresh_payload.get("attempted_count"),
        "successful_count": refresh_payload.get("successful_count"),
        "failed_count": refresh_payload.get("failed_count"),
        "skipped_count": refresh_payload.get("skipped_count"),
    }
    assert "attempted_count" in refresh_payload
    assert "successful_count" in refresh_payload
    assert "failed_count" in refresh_payload
    assert "skipped_count" in refresh_payload

    # 2) Build (create DPP)
    create_payload = {
        "asset_ids": {
            "manufacturerPartId": "CI-DEMO-PART-001",
            "serialNumber": "CI-DEMO-SN-001",
        },
        "selected_templates": ["digital-nameplate", "technical-data"],
    }
    create = api_client.post(
        f"/api/v1/tenants/{runtime.tenant_slug}/dpps",
        json=create_payload,
    )
    assert create.status_code in (200, 201), create.text
    dpp_id = _extract_dpp_id(create.json())
    report["steps"]["build"] = {"dpp_id": dpp_id, "status_code": create.status_code}

    # 3) Verify revision provenance is present for new revisions
    revisions_resp = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/dpps/{dpp_id}/revisions"
    )
    assert revisions_resp.status_code == 200, revisions_resp.text
    revisions = revisions_resp.json()
    assert revisions, "Expected at least one revision after create"
    assert "template_provenance" in revisions[0]
    report["steps"]["revisions"] = {
        "count": len(revisions),
        "has_template_provenance": "template_provenance" in revisions[0],
    }

    # 4) Publish DPP before export checks
    publish_resp = api_client.post(f"/api/v1/tenants/{runtime.tenant_slug}/dpps/{dpp_id}/publish")
    assert publish_resp.status_code == 200, publish_resp.text
    report["steps"]["publish"] = {"status_code": publish_resp.status_code}

    # 5) Export JSON
    export_json = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "json"},
    )
    assert export_json.status_code == 200, export_json.text
    json_path = artifacts / f"{dpp_id}.aas.json"
    _save_json(json_path, export_json.json())

    # 6) Export AASX
    export_aasx = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "aasx"},
    )
    assert export_aasx.status_code == 200, export_aasx.text
    aasx_path = artifacts / f"{dpp_id}.aasx"
    _save_bytes(aasx_path, export_aasx.content)

    with zipfile.ZipFile(aasx_path, "r") as zf:
        names = zf.namelist()
        assert names, "Exported AASX is empty"
        report["steps"]["export"] = {
            "json_path": str(json_path),
            "aasx_path": str(aasx_path),
            "aasx_entries": len(names),
        }

    # 7) Export XML, JSON-LD, and Turtle
    export_xml = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "xml"},
    )
    assert export_xml.status_code == 200, export_xml.text
    xml_path = artifacts / f"{dpp_id}.aas.xml"
    _save_bytes(xml_path, export_xml.content)
    assert xml_path.stat().st_size > 0

    export_jsonld = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "jsonld"},
    )
    assert export_jsonld.status_code == 200, export_jsonld.text
    jsonld_path = artifacts / f"{dpp_id}.aas.jsonld"
    _save_bytes(jsonld_path, export_jsonld.content)
    assert jsonld_path.stat().st_size > 0

    export_turtle = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "turtle"},
    )
    assert export_turtle.status_code == 200, export_turtle.text
    turtle_path = artifacts / f"{dpp_id}.aas.ttl"
    _save_bytes(turtle_path, export_turtle.content)
    assert turtle_path.stat().st_size > 0

    report["steps"]["export_extended"] = {
        "xml_path": str(xml_path),
        "jsonld_path": str(jsonld_path),
        "turtle_path": str(turtle_path),
    }

    # 8) Optional compliance check (if tool installed)
    compliance = {"json_ok": None, "aasx_ok": None}
    compliance_cmd = _resolve_compliance_cmd()
    if compliance_cmd:
        json_ok, json_output = _run_compliance_tool(compliance_cmd, json_path, is_aasx=False)
        aasx_ok, aasx_output = _run_compliance_tool(compliance_cmd, aasx_path, is_aasx=True)
        compliance["json_ok"] = json_ok
        compliance["aasx_ok"] = aasx_ok
        _save_json(
            artifacts / f"{dpp_id}.compliance.json.log.json",
            {"ok": json_ok, "output": json_output},
        )
        _save_json(
            artifacts / f"{dpp_id}.compliance.aasx.log.json",
            {"ok": aasx_ok, "output": aasx_output},
        )
        # If compliance tool is present, enforce AASX deserialization success
        assert aasx_ok, "AASX compliance check failed; see compliance logs"

    report["steps"]["compliance"] = compliance

    # 9) Write report
    report_path = artifacts / "pipeline-report.json"
    _save_json(report_path, report)
    report["artifacts"]["report_path"] = str(report_path)
