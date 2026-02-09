"""Tests for enhanced audit.py with hash chain support."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.audit import _build_event_data, _has_hash_columns, emit_audit_event


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


class TestAdvisoryLock:
    """Tests for pg_advisory_xact_lock in hash chain computation (H-8)."""

    @pytest.mark.asyncio
    async def test_advisory_lock_acquired_with_tenant_id(self) -> None:
        """emit_audit_event should acquire a per-tenant advisory lock."""
        tenant_id = uuid4()
        mock_session = AsyncMock()

        # Mock the SELECT result (no previous events)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("app.core.audit._has_hash_columns", return_value=True):
            await emit_audit_event(
                db_session=mock_session,
                action="create_dpp",
                resource_type="dpp",
                resource_id="test-123",
                tenant_id=tenant_id,
            )

        # Find the advisory lock call among all execute calls
        lock_call_found = False
        for call in mock_session.execute.call_args_list:
            args = call.args
            if args and hasattr(args[0], "text"):
                sql_text = str(args[0].text)
                if "pg_advisory_xact_lock" in sql_text:
                    lock_call_found = True
                    assert "hashtext(:tid)" in sql_text
                    break
        assert lock_call_found, "Advisory lock SQL not found in execute calls"

    @pytest.mark.asyncio
    async def test_advisory_lock_uses_fixed_key_for_platform_events(self) -> None:
        """Platform events (tenant_id=None) should use fixed lock key 0."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("app.core.audit._has_hash_columns", return_value=True):
            await emit_audit_event(
                db_session=mock_session,
                action="platform_action",
                resource_type="system",
                tenant_id=None,
            )

        lock_call_found = False
        for call in mock_session.execute.call_args_list:
            args = call.args
            if args and hasattr(args[0], "text"):
                sql_text = str(args[0].text)
                if "pg_advisory_xact_lock" in sql_text:
                    lock_call_found = True
                    assert "pg_advisory_xact_lock(0)" in sql_text
                    break
        assert lock_call_found, "Advisory lock SQL not found in execute calls"
