"""Tests for dead letter recorder — uses mock session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.opcua_agent.deadletter import record_dead_letter


@pytest.mark.asyncio
async def test_record_dead_letter_creates_new_row() -> None:
    """When no existing dead letter for (tenant, mapping), creates a new row."""
    session = AsyncMock()
    # session.add is synchronous on real AsyncSession
    session.add = MagicMock()
    # scalars().first() returns None → no existing row
    result_mock = MagicMock()
    result_mock.first.return_value = None
    session.scalars.return_value = result_mock

    tenant_id = uuid4()
    mapping_id = uuid4()

    await record_dead_letter(
        session=session,
        tenant_id=tenant_id,
        mapping_id=mapping_id,
        value_payload={"raw": 42},
        error="Type mismatch",
    )

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.tenant_id == tenant_id
    assert added.mapping_id == mapping_id
    assert added.error == "Type mismatch"
    assert added.count == 1
    assert added.value_payload == {"raw": 42}
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_dead_letter_increments_existing() -> None:
    """When a dead letter already exists, increment count and update fields."""
    session = AsyncMock()

    existing = MagicMock()
    existing.count = 3
    existing.error = "old error"
    existing.value_payload = {"old": True}
    existing.last_seen_at = None

    result_mock = MagicMock()
    result_mock.first.return_value = existing
    session.scalars.return_value = result_mock

    tenant_id = uuid4()
    mapping_id = uuid4()

    await record_dead_letter(
        session=session,
        tenant_id=tenant_id,
        mapping_id=mapping_id,
        value_payload={"raw": 99},
        error="New error",
    )

    assert existing.count == 4
    assert existing.error == "New error"
    assert existing.value_payload == {"raw": 99}
    assert existing.last_seen_at is not None
    # Should NOT call add — just update existing
    session.add.assert_not_called()
    session.flush.assert_awaited_once()
