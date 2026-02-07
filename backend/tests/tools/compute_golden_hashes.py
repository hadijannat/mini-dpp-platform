"""Compute golden hashes locally without a running server.

Fetches templates from the IDTA GitHub repo, parses with BaSyx,
builds definitions and schemas, and updates golden files in-place.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import httpx

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_dir))

from app.modules.templates.basyx_parser import BasyxTemplateParser
from app.modules.templates.catalog import TEMPLATE_CATALOG, TemplateDescriptor
from app.modules.templates.definition import TemplateDefinitionBuilder
from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter

GOLDENS_DIR = backend_dir / "tests" / "goldens" / "templates"
REPO_API = "https://api.github.com/repos/admin-shell-io/submodel-templates/contents/published"
RAW_BASE = "https://raw.githubusercontent.com/admin-shell-io/submodel-templates/main/published"
REF = "main"


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def sort_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_dict(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [sort_dict(item) for item in value]
    return value


def normalize_template_json(payload: dict[str, Any], template_key: str) -> dict[str, Any]:
    if "submodels" in payload or "assetAdministrationShells" in payload:
        normalized = sort_dict(payload)
    else:
        submodel = payload.get("submodel") if isinstance(payload.get("submodel"), dict) else payload
        if not isinstance(submodel, dict):
            raise ValueError("template_json_missing_submodel")
        if not submodel.get("idShort"):
            submodel["idShort"] = template_key.replace("-", "_").title().replace("_", "")
        environment = {
            "assetAdministrationShells": [],
            "submodels": [submodel],
            "conceptDescriptions": payload.get("conceptDescriptions", []),
        }
        normalized = sort_dict(environment)

    normalized.setdefault("assetAdministrationShells", [])
    normalized.setdefault("submodels", [])
    normalized.setdefault("conceptDescriptions", [])
    return normalized


def resolve_template_json_url(descriptor: TemplateDescriptor, version: str) -> str | None:
    """Try to resolve the JSON download URL from the GitHub API."""
    major, minor, patch = version.split(".")
    api_url = f"{REPO_API}/{descriptor.repo_folder}/{major}/{minor}/{patch}?ref={REF}"
    try:
        resp = httpx.get(
            api_url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "mini-dpp-platform"},
            timeout=30.0,
        )
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        print(f"  API resolve failed: {e}")
        return None

    if not isinstance(items, list):
        return None

    json_files = [i for i in items if str(i.get("name", "")).lower().endswith(".json")]
    # Prefer template files
    for f in json_files:
        name = str(f.get("name", "")).lower()
        if "template" in name or "submodel" in name:
            return f.get("download_url")
    if json_files:
        return json_files[0].get("download_url")
    return None


def fetch_template_json(descriptor: TemplateDescriptor, version: str) -> dict[str, Any] | None:
    """Fetch and normalize template JSON for a given descriptor and version."""
    url = resolve_template_json_url(descriptor, version)
    if url:
        print(f"  Fetching JSON from: {url}")
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        return normalize_template_json(resp.json(), descriptor.key)

    # Fallback: try raw URL
    major, minor, patch = version.split(".")
    json_pattern = descriptor.resolve_json_pattern()
    file_name = json_pattern.format(major=major, minor=minor, patch=patch)
    raw_url = f"{RAW_BASE}/{descriptor.repo_folder}/{major}/{minor}/{patch}/{file_name}"
    print(f"  Fallback raw URL: {raw_url}")
    try:
        resp = httpx.get(raw_url, timeout=30.0)
        resp.raise_for_status()
        return normalize_template_json(resp.json(), descriptor.key)
    except Exception as e:
        print(f"  Fallback failed: {e}")
        return None


def main() -> None:
    parser = BasyxTemplateParser()
    builder = TemplateDefinitionBuilder()
    converter = DefinitionToSchemaConverter()

    for golden_path in sorted(GOLDENS_DIR.glob("*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        key = golden["key"]
        version = golden["idta_version"]
        descriptor = TEMPLATE_CATALOG.get(key)
        if descriptor is None:
            print(f"SKIP {key}: not in catalog")
            continue

        print(f"\n=== {key}@{version} ===")

        aas_env = fetch_template_json(descriptor, version)
        if aas_env is None:
            print(f"  FAILED to fetch template JSON")
            continue

        # Parse with BaSyx
        json_bytes = json.dumps(aas_env).encode("utf-8")
        parsed = parser.parse_json(json_bytes, expected_semantic_id=descriptor.semantic_id)

        # Build definition
        definition = builder.build_definition(
            template_key=key,
            parsed=parsed,
            idta_version=version,
            semantic_id=descriptor.semantic_id,
        )

        # Derive schema
        schema = converter.convert(definition)

        # Compute hashes
        def_hash = sha256_json(definition)
        schema_hash = sha256_json(schema)

        old_def = golden["expected"]["definition_sha256"]
        old_schema = golden["expected"]["schema_sha256"]

        if def_hash != old_def:
            print(f"  definition_sha256: {old_def} -> {def_hash}")
        else:
            print(f"  definition_sha256: unchanged")

        if schema_hash != old_schema:
            print(f"  schema_sha256:     {old_schema} -> {schema_hash}")
        else:
            print(f"  schema_sha256:     unchanged")

        # Update golden file
        golden["expected"]["definition_sha256"] = def_hash
        golden["expected"]["schema_sha256"] = schema_hash
        golden_path.write_text(
            json.dumps(golden, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print("\nDone. Golden files updated.")


if __name__ == "__main__":
    main()
