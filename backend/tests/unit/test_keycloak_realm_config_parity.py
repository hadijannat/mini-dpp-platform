"""Regression checks for Keycloak realm auth settings parity."""

from __future__ import annotations

import json
from pathlib import Path


def _load_realm(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scope_by_name(realm: dict[str, object], scope_name: str) -> dict[str, object]:
    scopes = realm.get("clientScopes", [])
    assert isinstance(scopes, list)
    for scope in scopes:
        if isinstance(scope, dict) and scope.get("name") == scope_name:
            return scope
    raise AssertionError(f"Client scope '{scope_name}' not found")


def _protocol_mapper_names(scope: dict[str, object]) -> set[str]:
    protocol_mappers = scope.get("protocolMappers", [])
    if not isinstance(protocol_mappers, list):
        return set()
    names = {
        str(mapper.get("name"))
        for mapper in protocol_mappers
        if isinstance(mapper, dict) and mapper.get("name")
    }
    return names


def test_keycloak_realm_exports_enforce_email_verification_and_required_scopes() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    local_realm_path = backend_root / "../infra/keycloak/realm-export/dpp-platform-realm.json"
    prod_realm_path = (
        backend_root / "../infra/keycloak/realm-export-prod/dpp-platform-realm-prod.json"
    )

    local_realm = _load_realm(local_realm_path.resolve())
    prod_realm = _load_realm(prod_realm_path.resolve())

    # Email verification should be strict in all realm variants.
    assert local_realm.get("verifyEmail") is True
    assert prod_realm.get("verifyEmail") is True

    # Both exports should default new users to viewer role.
    assert "viewer" in (local_realm.get("defaultRoles") or [])
    assert "viewer" in (prod_realm.get("defaultRoles") or [])

    # Token claims required by onboarding must stay present.
    local_email_scope = _scope_by_name(local_realm, "email")
    prod_email_scope = _scope_by_name(prod_realm, "email")
    local_mappers = _protocol_mapper_names(local_email_scope)
    prod_mappers = _protocol_mapper_names(prod_email_scope)
    assert "email" in local_mappers
    assert "email verified" in local_mappers
    assert "email" in prod_mappers
    assert "email verified" in prod_mappers
