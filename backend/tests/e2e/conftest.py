from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest


@dataclass(frozen=True)
class RuntimeConfig:
    dpp_base_url: str
    keycloak_base_url: str
    realm: str
    client_id: str
    client_secret: str
    username: str
    password: str
    tenant_slug: str
    admin_username: str
    admin_password: str


@pytest.fixture(scope="session")
def runtime() -> RuntimeConfig:
    return RuntimeConfig(
        dpp_base_url=os.getenv("DPP_BASE_URL", "http://localhost:8000"),
        keycloak_base_url=os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8081"),
        realm=os.getenv("KEYCLOAK_REALM", "dpp-platform"),
        client_id=os.getenv("KEYCLOAK_CLIENT_ID", "dpp-backend"),
        client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET", "backend-secret-dev"),
        username=os.getenv("DPP_USERNAME", "publisher"),
        password=os.getenv("DPP_PASSWORD", "publisher123"),
        tenant_slug=os.getenv("DPP_TENANT", "default"),
        admin_username=os.getenv("DPP_ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("DPP_ADMIN_PASSWORD", "admin123"),
    )


@pytest.fixture(scope="session")
def test_results_dir() -> Path:
    path = Path(os.getenv("PIPELINE_REPORT_DIR", "test-results")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def wait_for_http_ok(url: str, timeout_s: int = 90, interval_s: float = 1.0) -> None:
    deadline = time.time() + timeout_s
    last_err: str | None = None

    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=5.0, follow_redirects=True)
            if response.status_code < 500:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = repr(exc)
        time.sleep(interval_s)

    raise RuntimeError(f"Timed out waiting for {url}. Last error: {last_err}")


def _get_oidc_token(runtime: RuntimeConfig, username: str, password: str) -> str:
    wait_for_http_ok(f"{runtime.keycloak_base_url}/realms/{runtime.realm}")

    token_url = f"{runtime.keycloak_base_url}/realms/{runtime.realm}/protocol/openid-connect/token"
    data = {
        "client_id": runtime.client_id,
        "client_secret": runtime.client_secret,
        "username": username,
        "password": password,
        "grant_type": "password",
    }

    response = httpx.post(token_url, data=data, timeout=30.0)
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"Missing access_token in Keycloak response: {payload}")
    return token


def _extract_token_sub(token: str) -> str:
    import base64
    import json

    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
    subject = data.get("sub")
    if not subject:
        raise RuntimeError("Missing sub in token payload")
    return str(subject)


@pytest.fixture(scope="session")
def oidc_token(runtime: RuntimeConfig) -> str:
    return _get_oidc_token(runtime, runtime.username, runtime.password)


@pytest.fixture(scope="session")
def admin_token(runtime: RuntimeConfig) -> str:
    return _get_oidc_token(runtime, runtime.admin_username, runtime.admin_password)


@pytest.fixture(scope="session")
def ensure_publisher_membership(
    runtime: RuntimeConfig,
    admin_token: str,
    oidc_token: str,
) -> str:
    wait_for_http_ok(f"{runtime.dpp_base_url}/api/v1/docs")

    publisher_sub = _extract_token_sub(oidc_token)
    headers = {"Authorization": f"Bearer {admin_token}"}
    client = httpx.Client(base_url=runtime.dpp_base_url, headers=headers, timeout=30.0)
    try:
        response = client.post(
            f"/api/v1/tenants/{runtime.tenant_slug}/members",
            json={"user_subject": publisher_sub, "role": "publisher"},
        )
    finally:
        client.close()

    if response.status_code not in (200, 201, 409):
        raise RuntimeError(
            f"Failed to ensure publisher membership: {response.status_code} {response.text}"
        )

    return publisher_sub


@pytest.fixture(scope="session")
def api_client(
    runtime: RuntimeConfig,
    oidc_token: str,
    ensure_publisher_membership: str,
) -> httpx.Client:
    _ = ensure_publisher_membership
    wait_for_http_ok(f"{runtime.dpp_base_url}/api/v1/docs")

    headers = {"Authorization": f"Bearer {oidc_token}"}
    client = httpx.Client(base_url=runtime.dpp_base_url, headers=headers, timeout=60.0)
    try:
        yield client
    finally:
        client.close()
