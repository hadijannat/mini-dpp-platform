"""Tests for OPC UA connection lifecycle manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.opcua_agent.connection_manager import ConnectionManager


@pytest.mark.asyncio
@patch("app.opcua_agent.connection_manager.Client")
async def test_connect_and_disconnect(mock_client_cls: MagicMock) -> None:
    """Connect creates a client, disconnect tears it down."""
    mock_client = AsyncMock()
    mock_client_cls.return_value = mock_client

    mgr = ConnectionManager(max_per_tenant=5)
    tenant_id = uuid4()
    source_id = uuid4()

    await mgr.connect(
        source_id=source_id,
        tenant_id=tenant_id,
        endpoint_url="opc.tcp://localhost:4840",
    )

    mock_client.connect.assert_awaited_once()
    assert mgr.connection_count(tenant_id) == 1
    assert mgr.get_client(source_id) is mock_client

    await mgr.disconnect(source_id)
    mock_client.disconnect.assert_awaited_once()
    assert mgr.connection_count(tenant_id) == 0
    assert mgr.get_client(source_id) is None


@pytest.mark.asyncio
@patch("app.opcua_agent.connection_manager.Client")
async def test_enforces_tenant_limit(mock_client_cls: MagicMock) -> None:
    """Exceeding max_per_tenant raises ValueError."""
    mock_client = AsyncMock()
    mock_client_cls.return_value = mock_client

    mgr = ConnectionManager(max_per_tenant=1)
    tenant_id = uuid4()

    await mgr.connect(
        source_id=uuid4(),
        tenant_id=tenant_id,
        endpoint_url="opc.tcp://localhost:4840",
    )

    with pytest.raises(ValueError, match="limit"):
        await mgr.connect(
            source_id=uuid4(),
            tenant_id=tenant_id,
            endpoint_url="opc.tcp://localhost:4841",
        )
