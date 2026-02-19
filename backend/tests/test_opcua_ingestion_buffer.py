"""Tests for in-memory coalescing ingestion buffer."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.opcua_agent.ingestion_buffer import IngestionBuffer


@pytest.mark.asyncio
async def test_put_and_drain_overwrites() -> None:
    """Latest value for the same key wins; drain returns exactly one entry."""
    buf = IngestionBuffer()

    tenant = uuid4()
    dpp = uuid4()
    mapping = uuid4()
    sm_id = "submodel-1"
    path = "Temperature"

    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping,
        target_submodel_id=sm_id,
        target_aas_path=path,
        value=42.0,
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
    )
    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping,
        target_submodel_id=sm_id,
        target_aas_path=path,
        value=99.0,
        timestamp=datetime(2025, 1, 2, tzinfo=UTC),
    )

    entries = await buf.drain()
    assert len(entries) == 1
    assert entries[0].value == 99.0
    assert entries[0].timestamp == datetime(2025, 1, 2, tzinfo=UTC)

    # After drain, buffer is empty
    assert buf.size() == 0
    assert await buf.drain() == []


@pytest.mark.asyncio
async def test_size() -> None:
    """Size reflects current buffer occupancy."""
    buf = IngestionBuffer()
    assert buf.size() == 0

    tenant = uuid4()
    dpp = uuid4()
    mapping = uuid4()

    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping,
        target_submodel_id="sm-1",
        target_aas_path="A",
        value=1,
        timestamp=datetime.now(UTC),
    )
    assert buf.size() == 1

    # Same key — size stays 1
    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping,
        target_submodel_id="sm-1",
        target_aas_path="A",
        value=2,
        timestamp=datetime.now(UTC),
    )
    assert buf.size() == 1


@pytest.mark.asyncio
async def test_multiple_keys() -> None:
    """Distinct keys produce distinct entries on drain."""
    buf = IngestionBuffer()

    tenant = uuid4()
    dpp = uuid4()
    mapping1 = uuid4()
    mapping2 = uuid4()

    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping1,
        target_submodel_id="sm-1",
        target_aas_path="Temp",
        value=20,
        timestamp=datetime.now(UTC),
    )
    await buf.put(
        tenant_id=tenant,
        dpp_id=dpp,
        mapping_id=mapping2,
        target_submodel_id="sm-2",
        target_aas_path="Pressure",
        value=101,
        timestamp=datetime.now(UTC),
    )

    assert buf.size() == 2
    entries = await buf.drain()
    assert len(entries) == 2
    paths = {e.target_aas_path for e in entries}
    assert paths == {"Temp", "Pressure"}
