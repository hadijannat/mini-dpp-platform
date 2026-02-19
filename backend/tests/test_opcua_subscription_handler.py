"""Tests for OPC UA subscription and data change handling."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.opcua_agent.ingestion_buffer import IngestionBuffer
from app.opcua_agent.subscription_handler import DataChangeHandler


@pytest.mark.asyncio
async def test_puts_to_buffer() -> None:
    """A data change notification puts the value into the buffer."""
    buffer = IngestionBuffer()
    tenant_id = uuid4()
    dpp_id = uuid4()
    mapping_id = uuid4()

    handler = DataChangeHandler(
        buffer=buffer,
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        mapping_id=mapping_id,
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        transform_expr=None,
    )

    await handler.datachange_notification(node=None, val=42.5, data=None)

    entries = await buffer.drain()
    assert len(entries) == 1
    assert entries[0].value == 42.5
    assert entries[0].tenant_id == tenant_id
    assert entries[0].dpp_id == dpp_id
    assert entries[0].mapping_id == mapping_id
    assert entries[0].target_submodel_id == "sm-1"
    assert entries[0].target_aas_path == "Temperature"


@pytest.mark.asyncio
async def test_applies_transform() -> None:
    """Transform expression is applied before buffering."""
    buffer = IngestionBuffer()
    handler = DataChangeHandler(
        buffer=buffer,
        tenant_id=uuid4(),
        dpp_id=uuid4(),
        mapping_id=uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature",
        transform_expr="scale:0.001|round:2",
    )

    await handler.datachange_notification(node=None, val=12345, data=None)

    entries = await buffer.drain()
    assert len(entries) == 1
    assert entries[0].value == 12.35
