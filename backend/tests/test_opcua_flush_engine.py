"""Tests for the batch flush engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.opcua_agent.ingestion_buffer import BufferEntry, IngestionBuffer


@pytest.mark.asyncio
async def test_group_entries_by_dpp() -> None:
    """Entries are grouped by (tenant_id, dpp_id) composite key."""
    from app.opcua_agent.flush_engine import _group_entries_by_dpp

    tid = uuid.uuid4()
    dpp1, dpp2 = uuid.uuid4(), uuid.uuid4()
    entries = [
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp1,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Temp",
            value=22.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp1,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Humidity",
            value=55.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp2,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-2",
            target_aas_path="Pressure",
            value=1013.0,
            timestamp=datetime.now(tz=UTC),
        ),
    ]
    grouped = _group_entries_by_dpp(entries)
    assert len(grouped) == 2
    assert len(grouped[(tid, dpp1)]) == 2
    assert len(grouped[(tid, dpp2)]) == 1


@pytest.mark.asyncio
async def test_build_patch_operations() -> None:
    """Entries are grouped by submodel_id with set_value operations."""
    from app.opcua_agent.flush_engine import _build_patch_operations

    entry = BufferEntry(
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature.Value",
        value=22.5,
        timestamp=datetime.now(tz=UTC),
    )
    ops = _build_patch_operations([entry])
    assert len(ops) == 1
    assert ops[0]["submodel_id"] == "sm-1"
    assert ops[0]["operations"][0]["op"] == "set_value"
    assert ops[0]["operations"][0]["path"] == "Temperature.Value"
    assert ops[0]["operations"][0]["value"] == 22.5


@pytest.mark.asyncio
async def test_build_patch_operations_multiple_submodels() -> None:
    """Entries targeting different submodels produce separate patch groups."""
    from app.opcua_agent.flush_engine import _build_patch_operations

    tid = uuid.uuid4()
    dpp_id = uuid.uuid4()
    entries = [
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp_id,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Temp",
            value=22.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp_id,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-2",
            target_aas_path="Pressure",
            value=1013.0,
            timestamp=datetime.now(tz=UTC),
        ),
        BufferEntry(
            tenant_id=tid,
            dpp_id=dpp_id,
            mapping_id=uuid.uuid4(),
            target_submodel_id="sm-1",
            target_aas_path="Humidity",
            value=55.0,
            timestamp=datetime.now(tz=UTC),
        ),
    ]
    ops = _build_patch_operations(entries)
    assert len(ops) == 2
    sm_ids = {op["submodel_id"] for op in ops}
    assert sm_ids == {"sm-1", "sm-2"}
    # sm-1 should have 2 operations
    sm1_ops = [op for op in ops if op["submodel_id"] == "sm-1"][0]
    assert len(sm1_ops["operations"]) == 2


@pytest.mark.asyncio
async def test_flush_single_dpp_returns_retry_on_lock_contention() -> None:
    """Lock contention should keep entries retryable."""
    from app.opcua_agent.flush_engine import _flush_single_dpp

    mock_session = AsyncMock()
    lock_result = MagicMock()
    lock_result.scalar.return_value = False
    mock_session.execute.return_value = lock_result

    outcome = await _flush_single_dpp(
        session=mock_session,
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        entries=[],
    )
    assert outcome.status == "retry"
    assert "Advisory lock unavailable" in (outcome.reason or "")


@pytest.mark.asyncio
async def test_flush_single_dpp_deadletters_when_dpp_missing() -> None:
    """Missing DPP should return terminal deadletter outcome."""
    from app.opcua_agent.flush_engine import _flush_single_dpp

    mock_session = AsyncMock()
    lock_result = MagicMock()
    lock_result.scalar.return_value = True
    mock_session.execute.return_value = lock_result
    mock_session.get.return_value = None

    outcome = await _flush_single_dpp(
        session=mock_session,
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        entries=[],
    )
    assert outcome.status == "deadletter"
    assert "not found" in (outcome.reason or "")


@pytest.mark.asyncio
async def test_flush_single_dpp_deadletters_when_no_revision() -> None:
    """A DPP with no revisions cannot be patched and must deadletter."""
    from app.opcua_agent.flush_engine import _flush_single_dpp

    mock_session = AsyncMock()
    lock_result = MagicMock()
    lock_result.scalar.return_value = True
    mock_session.execute.return_value = lock_result
    mock_session.get.return_value = MagicMock()
    scalars_result = MagicMock()
    scalars_result.first.return_value = None
    mock_session.scalars.return_value = scalars_result

    outcome = await _flush_single_dpp(
        session=mock_session,
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        entries=[],
    )
    assert outcome.status == "deadletter"
    assert "no revisions" in (outcome.reason or "").lower()


class _DummyTxn:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummySession:
    def begin(self):
        return _DummyTxn()


class _DummySessionCtx:
    async def __aenter__(self):
        return _DummySession()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _dummy_session_factory():
    return _DummySessionCtx()


@pytest.mark.asyncio
async def test_flush_buffer_requeues_retryable_entries() -> None:
    """Retryable outcomes should be put back into the ingestion buffer."""
    from app.opcua_agent.flush_engine import FlushOutcome, flush_buffer

    entry = BufferEntry(
        tenant_id=uuid.uuid4(),
        dpp_id=uuid.uuid4(),
        mapping_id=uuid.uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature.Value",
        value=42.0,
        timestamp=datetime.now(tz=UTC),
    )
    buffer = IngestionBuffer()
    await buffer.put_entry(entry)

    with patch(
        "app.opcua_agent.flush_engine._flush_single_dpp",
        new=AsyncMock(return_value=FlushOutcome(status="retry", reason="lock")),
    ):
        flushed = await flush_buffer(buffer, _dummy_session_factory)  # type: ignore[arg-type]

    assert flushed == 0
    assert buffer.size() == 1
