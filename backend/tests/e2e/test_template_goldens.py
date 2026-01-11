from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256_json(obj: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(obj)).hexdigest()


def _load_goldens(goldens_dir: Path) -> dict[str, dict[str, Any]]:
    templates_dir = goldens_dir / "templates"
    if not templates_dir.exists():
        raise AssertionError(f"Missing goldens folder: {templates_dir}")

    out: dict[str, dict[str, Any]] = {}
    for path in templates_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["key"]] = data
    if not out:
        raise AssertionError(f"No golden template files found in {templates_dir}")
    return out


@pytest.mark.e2e
@pytest.mark.golden
def test_templates_match_goldens(api_client: httpx.Client) -> None:
    goldens = _load_goldens(Path(__file__).resolve().parents[1] / "goldens")

    refresh = api_client.post("/api/v1/templates/refresh")
    assert refresh.status_code in (200, 201), refresh.text

    for key, golden in goldens.items():
        meta = api_client.get(f"/api/v1/templates/{key}")
        assert meta.status_code == 200, meta.text
        meta_payload = meta.json()

        assert meta_payload.get("idta_version") == golden["idta_version"], (
            f"idta_version mismatch for {key}"
        )
        assert meta_payload.get("semantic_id") == golden["semantic_id"], (
            f"semantic_id mismatch for {key}"
        )

        definition_resp = api_client.get(f"/api/v1/templates/{key}/definition")
        assert definition_resp.status_code == 200, definition_resp.text
        definition_payload = definition_resp.json()
        definition = definition_payload.get("definition")
        if definition is None:
            raise AssertionError(f"Definition missing for {key}: {definition_payload}")

        schema_resp = api_client.get(f"/api/v1/templates/{key}/schema")
        assert schema_resp.status_code == 200, schema_resp.text
        schema_payload = schema_resp.json()
        schema = schema_payload.get("schema")
        if schema is None:
            raise AssertionError(f"Schema missing for {key}: {schema_payload}")

        definition_hash = _sha256_json(definition)
        schema_hash = _sha256_json(schema)

        expected_def = golden["expected"]["definition_sha256"]
        expected_schema = golden["expected"]["schema_sha256"]

        assert expected_def != "REPLACE_WITH_UPDATE_SCRIPT_OUTPUT", (
            f"Golden file for {key} not initialized. Run update_template_goldens.py."
        )
        assert expected_schema != "REPLACE_WITH_UPDATE_SCRIPT_OUTPUT", (
            f"Golden file for {key} not initialized. Run update_template_goldens.py."
        )

        assert definition_hash == expected_def, f"Definition hash mismatch for {key}"
        assert schema_hash == expected_schema, f"Schema hash mismatch for {key}"
