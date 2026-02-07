"""
Unit tests for audit event emission.

Tests that emit_audit_event writes AuditEvent records correctly and
handles errors gracefully (no exception propagation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.audit import emit_audit_event
from app.core.security.oidc import TokenPayload


def _make_user(sub: str = "user-123") -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email="test@example.com",
        preferred_username="testuser",
        roles=["publisher"],
        bpn=None,
        org=None,
        clearance=None,
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


def _make_request(ip: str = "10.0.0.1", ua: str = "TestAgent/1.0") -> MagicMock:
    req = MagicMock()
    req.client.host = ip
    req.headers = {"user-agent": ua}
    return req


@pytest.mark.asyncio
async def test_emit_audit_event_writes_record() -> None:
    """emit_audit_event should add an AuditEvent to the session and flush."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    user = _make_user()
    tenant_id = uuid4()
    resource_id = uuid4()
    request = _make_request()

    await emit_audit_event(
        db_session=session,
        action="create_dpp",
        resource_type="dpp",
        resource_id=resource_id,
        tenant_id=tenant_id,
        user=user,
        decision="allow",
        request=request,
        metadata={"key": "value"},
    )

    session.add.assert_called_once()
    event = session.add.call_args[0][0]
    assert event.action == "create_dpp"
    assert event.resource_type == "dpp"
    assert event.resource_id == str(resource_id)
    assert event.tenant_id == tenant_id
    assert event.subject == "user-123"
    assert event.decision == "allow"
    assert event.ip_address == "10.0.0.1"
    assert event.user_agent == "TestAgent/1.0"
    assert event.metadata_ == {"key": "value"}
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_audit_event_without_user() -> None:
    """System events should have subject=None."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    await emit_audit_event(
        db_session=session,
        action="system_migration",
        resource_type="database",
    )

    event = session.add.call_args[0][0]
    assert event.subject is None
    assert event.ip_address is None
    assert event.user_agent is None


@pytest.mark.asyncio
async def test_emit_audit_event_without_request() -> None:
    """When no request is provided, IP and user-agent should be None."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    user = _make_user()

    await emit_audit_event(
        db_session=session,
        action="delete_policy",
        resource_type="policy",
        resource_id=uuid4(),
        user=user,
    )

    event = session.add.call_args[0][0]
    assert event.subject == "user-123"
    assert event.ip_address is None
    assert event.user_agent is None


@pytest.mark.asyncio
async def test_emit_audit_event_swallows_db_errors() -> None:
    """A database failure during audit write must not propagate to the caller."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(side_effect=RuntimeError("DB connection lost"))

    # Should NOT raise — emit_audit_event catches exceptions.
    await emit_audit_event(
        db_session=session,
        action="create_dpp",
        resource_type="dpp",
        resource_id=uuid4(),
        user=_make_user(),
    )

    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_audit_event_deny_decision() -> None:
    """ABAC deny events should be recorded with decision='deny'."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    await emit_audit_event(
        db_session=session,
        action="abac_deny",
        resource_type="dpp",
        resource_id=uuid4(),
        user=_make_user(),
        decision="deny",
        metadata={"reason": "Insufficient clearance"},
    )

    event = session.add.call_args[0][0]
    assert event.action == "abac_deny"
    assert event.decision == "deny"
    assert event.metadata_ == {"reason": "Insufficient clearance"}
