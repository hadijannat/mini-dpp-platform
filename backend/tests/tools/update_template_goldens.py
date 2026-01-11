from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


BACKEND = os.getenv("DPP_BASE_URL", "http://localhost:8000")
KEYCLOAK = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8081")
REALM = os.getenv("KEYCLOAK_REALM", "dpp-platform")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "backend-secret-dev")
USERNAME = os.getenv("DPP_USERNAME", "publisher")
PASSWORD = os.getenv("DPP_PASSWORD", "publisher123")

HERE = Path(__file__).resolve()
BACKEND_DIR = HERE.parents[2]
GOLDENS_DIR = BACKEND_DIR / "tests" / "goldens" / "templates"


def get_token() -> str:
    url = f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token"
    response = httpx.post(
        url,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username": USERNAME,
            "password": PASSWORD,
            "grant_type": "password",
        },
        timeout=30.0,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(f"Missing access_token in Keycloak response: {response.json()}")
    return token


def main() -> None:
    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)

    token = get_token()
    client = httpx.Client(
        base_url=BACKEND,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )

    refresh = client.post("/api/v1/templates/refresh")
    refresh.raise_for_status()

    for golden_path in sorted(GOLDENS_DIR.glob("*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        key = golden.get("key")
        if not key:
            raise RuntimeError(f"Missing key in golden file: {golden_path}")

        meta = client.get(f"/api/v1/templates/{key}")
        meta.raise_for_status()
        meta_payload = meta.json()

        golden["idta_version"] = meta_payload.get("idta_version", golden.get("idta_version"))
        golden["semantic_id"] = meta_payload.get("semantic_id", golden.get("semantic_id"))

        definition_resp = client.get(f"/api/v1/templates/{key}/definition")
        definition_resp.raise_for_status()
        definition = definition_resp.json().get("definition")
        if definition is None:
            raise RuntimeError(f"Missing definition for {key}: {definition_resp.json()}")

        schema_resp = client.get(f"/api/v1/templates/{key}/schema")
        schema_resp.raise_for_status()
        schema = schema_resp.json().get("schema")
        if schema is None:
            raise RuntimeError(f"Missing schema for {key}: {schema_resp.json()}")

        golden.setdefault("expected", {})
        golden["expected"]["definition_sha256"] = sha256_json(definition)
        golden["expected"]["schema_sha256"] = sha256_json(schema)

        golden_path.write_text(
            json.dumps(golden, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Updated {golden_path.name}")

    print("Done. Commit the updated golden files.")


if __name__ == "__main__":
    main()
