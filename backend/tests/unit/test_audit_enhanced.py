"""Tests for enhanced audit.py with hash chain support."""

from __future__ import annotations

from typing import Any

from app.core.audit import _build_event_data, _has_hash_columns


class TestBuildEventData:
    """Tests for the canonical event data builder."""

    def test_minimal_fields(self) -> None:
        data = _build_event_data(
            action="create_dpp",
            resource_type="dpp",
            resource_id=None,
            tenant_id=None,
            subject=None,
            decision=None,
            ip_address=None,
            user_agent=None,
            metadata=None,
        )
        assert data == {"action": "create_dpp", "resource_type": "dpp"}

    def test_all_fields(self) -> None:
        data = _build_event_data(
            action="delete_policy",
            resource_type="policy",
            resource_id="abc-123",
            tenant_id="tenant-1",
            subject="user-sub",
            decision="allow",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            metadata={"reason": "test"},
        )
        assert data == {
            "action": "delete_policy",
            "resource_type": "policy",
            "resource_id": "abc-123",
            "tenant_id": "tenant-1",
            "subject": "user-sub",
            "decision": "allow",
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "metadata": {"reason": "test"},
        }

    def test_none_fields_excluded(self) -> None:
        """None values should not appear in the output dict."""
        data = _build_event_data(
            action="view",
            resource_type="dpp",
            resource_id="123",
            tenant_id=None,
            subject="user",
            decision=None,
            ip_address=None,
            user_agent=None,
            metadata=None,
        )
        assert "tenant_id" not in data
        assert "decision" not in data
        assert "ip_address" not in data
        assert "user_agent" not in data
        assert "metadata" not in data

    def test_deterministic(self) -> None:
        """Same input always produces same dict."""
        kwargs: dict[str, Any] = {
            "action": "test",
            "resource_type": "dpp",
            "resource_id": "abc",
            "tenant_id": "t1",
            "subject": "s1",
            "decision": "allow",
            "ip_address": "1.2.3.4",
            "user_agent": "ua",
            "metadata": {"key": "value"},
        }
        d1 = _build_event_data(**kwargs)
        d2 = _build_event_data(**kwargs)
        assert d1 == d2


class TestHasHashColumns:
    """Tests for hash column detection."""

    def test_current_model_has_hash_columns(self) -> None:
        """After migration 0011, the model should have hash chain columns."""
        assert _has_hash_columns() is True
