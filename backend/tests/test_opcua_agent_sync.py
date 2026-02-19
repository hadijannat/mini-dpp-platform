"""Tests for OPC UA agent subscription synchronization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.opcua_agent.ingestion_buffer import IngestionBuffer


@pytest.mark.asyncio
async def test_sync_subscriptions_creates_subscription() -> None:
    """A desired mapping should establish a live asyncua subscription."""
    from app.opcua_agent import main as agent_main

    agent_main._active_subscriptions.clear()
    mapping = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        dpp_id=uuid4(),
        target_submodel_id="sm-1",
        target_aas_path="Temperature.Value",
        value_transform_expr=None,
        sampling_interval_ms=250,
        opcua_node_id="ns=4;s=Temperature",
    )
    source = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        endpoint_url="opc.tcp://example.com:4840",
        security_policy=None,
        username=None,
        password_encrypted=None,
    )

    mock_subscription = AsyncMock()
    mock_subscription.subscribe_data_change = AsyncMock(return_value=101)
    mock_client = AsyncMock()
    mock_client.create_subscription = AsyncMock(return_value=mock_subscription)
    mock_client.get_node = MagicMock(return_value=object())

    conn_manager = MagicMock()
    conn_manager.connect = AsyncMock(return_value=mock_client)
    conn_manager.connected_source_ids = MagicMock(return_value={source.id})
    conn_manager.disconnect = AsyncMock()

    with (
        patch(
            "app.opcua_agent.main._load_desired_mappings",
            new=AsyncMock(return_value={mapping.id: (mapping, source)}),
        ),
        patch("app.opcua_agent.main.get_settings") as mock_settings,
    ):
        mock_settings.return_value.opcua_default_sampling_interval_ms = 1000
        mock_settings.return_value.encryption_master_key = "test-key"
        await agent_main._sync_subscriptions(
            AsyncMock(),  # session_factory is unused in this test due patching
            conn_manager,
            IngestionBuffer(),
        )

    assert mapping.id in agent_main._active_subscriptions
    mock_client.create_subscription.assert_awaited_once()
    mock_subscription.subscribe_data_change.assert_awaited_once()
    conn_manager.disconnect.assert_not_awaited()

    agent_main._active_subscriptions.clear()


@pytest.mark.asyncio
async def test_sync_subscriptions_removes_stale_and_disconnects_unused_source() -> None:
    """Stale subscriptions should be removed and unused sources disconnected."""
    from app.opcua_agent import main as agent_main

    mapping_id = uuid4()
    source_id = uuid4()
    stale_subscription = AsyncMock()
    stale_subscription.unsubscribe = AsyncMock()
    stale_subscription.delete = AsyncMock()
    agent_main._active_subscriptions.clear()
    agent_main._active_subscriptions[mapping_id] = agent_main._SubscriptionEntry(
        source_id=source_id,
        subscription=stale_subscription,
        handle=7,
    )

    conn_manager = MagicMock()
    conn_manager.connected_source_ids = MagicMock(return_value={source_id})
    conn_manager.disconnect = AsyncMock()

    with (
        patch(
            "app.opcua_agent.main._load_desired_mappings",
            new=AsyncMock(return_value={}),
        ),
        patch("app.opcua_agent.main.get_settings") as mock_settings,
    ):
        mock_settings.return_value.opcua_default_sampling_interval_ms = 1000
        mock_settings.return_value.encryption_master_key = "test-key"
        await agent_main._sync_subscriptions(
            AsyncMock(),  # session_factory is unused in this test due patching
            conn_manager,
            IngestionBuffer(),
        )

    stale_subscription.unsubscribe.assert_awaited_once_with(7)
    stale_subscription.delete.assert_awaited_once()
    conn_manager.disconnect.assert_awaited_once_with(source_id)
    assert mapping_id not in agent_main._active_subscriptions
