from __future__ import annotations

import importlib.util
import json
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


def _run_compliance_tool(file_path: Path, *, is_aasx: bool) -> tuple[bool, str]:
    exe = shutil.which("aas-compliance-check")
    if exe:
        cmd = [exe]
    else:
        python = shutil.which("python") or "python"
        cmd = [python, "-m", "aas_compliance_tool.cli"]

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
    report["steps"]["refresh"] = {"status_code": refresh.status_code}
    assert refresh.status_code in (200, 201), refresh.text

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

    # 3) Export JSON
    export_json = api_client.get(
        f"/api/v1/tenants/{runtime.tenant_slug}/export/{dpp_id}",
        params={"format": "json"},
    )
    assert export_json.status_code == 200, export_json.text
    json_path = artifacts / f"{dpp_id}.aas.json"
    _save_json(json_path, export_json.json())

    # 4) Export AASX
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

    # 5) Optional compliance check (if tool installed)
    compliance = {"json_ok": None, "aasx_ok": None}
    compliance_available = bool(
        shutil.which("aas-compliance-check") or importlib.util.find_spec("aas_compliance_tool")
    )
    if compliance_available:
        json_ok, json_output = _run_compliance_tool(json_path, is_aasx=False)
        aasx_ok, aasx_output = _run_compliance_tool(aasx_path, is_aasx=True)
        compliance["json_ok"] = json_ok
        compliance["aasx_ok"] = aasx_ok
        _save_json(
            artifacts / f"{dpp_id}.compliance.json.log.json", {"ok": json_ok, "output": json_output}
        )
        _save_json(
            artifacts / f"{dpp_id}.compliance.aasx.log.json", {"ok": aasx_ok, "output": aasx_output}
        )
        # If compliance tool is present, enforce AASX deserialization success
        assert aasx_ok, "AASX compliance check failed; see compliance logs"

    report["steps"]["compliance"] = compliance

    # 6) Write report
    report_path = artifacts / "pipeline-report.json"
    _save_json(report_path, report)
    report["artifacts"]["report_path"] = str(report_path)
