"""Unit tests for standardized ABAC resource context builders."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.core.security.resource_context import (
    build_connector_resource_context,
    build_dpp_resource_context,
)
from app.db.models import DPPStatus


def test_build_dpp_resource_context_defaults_visibility_scope() -> None:
    """DPP context should default visibility scope when legacy objects omit it."""
    dpp = SimpleNamespace(
        id=uuid4(),
        owner_subject="sub-owner",
        status=DPPStatus.DRAFT,
    )

    result = build_dpp_resource_context(dpp)

    assert result == {
        "type": "dpp",
        "id": str(dpp.id),
        "owner_subject": "sub-owner",
        "status": "draft",
        "visibility_scope": "owner_team",
        "shared_with_current_user": False,
    }


def test_build_connector_resource_context_uses_created_by_subject() -> None:
    """Connector context should use creator subject and preserve shared flag."""
    connector = SimpleNamespace(
        id=uuid4(),
        created_by_subject="sub-creator",
        status="active",
        visibility_scope="tenant",
    )

    result = build_connector_resource_context(connector, shared_with_current_user=True)

    assert result == {
        "type": "connector",
        "id": str(connector.id),
        "owner_subject": "sub-creator",
        "status": "active",
        "visibility_scope": "tenant",
        "shared_with_current_user": True,
    }


def test_build_connector_resource_context_falls_back_to_owner_subject() -> None:
    """Connector context should remain compatible with owner_subject-based mocks."""
    connector = SimpleNamespace(
        id=uuid4(),
        owner_subject="legacy-owner",
        status="active",
    )

    result = build_connector_resource_context(connector)

    assert result["owner_subject"] == "legacy-owner"
    assert result["visibility_scope"] == "owner_team"
