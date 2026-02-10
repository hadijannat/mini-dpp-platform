"""Standardized ABAC resource context builders."""

from __future__ import annotations

from typing import Any


def build_dpp_resource_context(
    dpp: Any,
    *,
    shared_with_current_user: bool = False,
) -> dict[str, Any]:
    """Build ABAC payload for a DPP resource."""
    raw_status = getattr(dpp, "status", "")
    status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    raw_visibility_scope = getattr(dpp, "visibility_scope", "owner_team")
    visibility_scope = (
        raw_visibility_scope.value
        if hasattr(raw_visibility_scope, "value")
        else raw_visibility_scope
    )
    return {
        "type": "dpp",
        "id": str(dpp.id),
        "owner_subject": dpp.owner_subject,
        "status": status,
        "visibility_scope": str(visibility_scope),
        "shared_with_current_user": shared_with_current_user,
    }


def build_connector_resource_context(
    connector: Any,
    *,
    shared_with_current_user: bool = False,
) -> dict[str, Any]:
    """Build ABAC payload for a connector resource."""
    raw_status = getattr(connector, "status", "")
    status = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
    raw_visibility_scope = getattr(connector, "visibility_scope", "owner_team")
    visibility_scope = (
        raw_visibility_scope.value
        if hasattr(raw_visibility_scope, "value")
        else raw_visibility_scope
    )
    owner_subject = getattr(
        connector,
        "created_by_subject",
        getattr(connector, "owner_subject", ""),
    )
    return {
        "type": "connector",
        "id": str(connector.id),
        "owner_subject": owner_subject,
        "status": status,
        "visibility_scope": str(visibility_scope),
        "shared_with_current_user": shared_with_current_user,
    }
