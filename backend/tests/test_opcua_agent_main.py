"""Tests for opcua_agent entry point — verifies graceful shutdown."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


def _mock_health_server():
    """Return patch context managers for the health server components."""
    mock_runner = AsyncMock()
    mock_runner.setup = AsyncMock()
    mock_runner.cleanup = AsyncMock()

    mock_site = AsyncMock()
    mock_site.start = AsyncMock()

    return (
        patch("app.opcua_agent.main.web.AppRunner", return_value=mock_runner),
        patch("app.opcua_agent.main.web.TCPSite", return_value=mock_site),
        mock_runner,
    )


@pytest.mark.asyncio
async def test_agent_exits_when_opcua_disabled() -> None:
    """Agent should exit immediately if opcua_enabled=False."""
    with patch("app.opcua_agent.main.get_settings") as mock_settings:
        mock_settings.return_value.opcua_enabled = False
        mock_settings.return_value.database_url = "postgresql+asyncpg://x@localhost/x"
        mock_settings.return_value.database_pool_size = 5
        mock_settings.return_value.database_max_overflow = 10
        mock_settings.return_value.database_pool_timeout = 30
        mock_settings.return_value.debug = False
        from app.opcua_agent.main import run_agent

        await run_agent(max_cycles=1)


@pytest.mark.asyncio
async def test_agent_runs_limited_cycles() -> None:
    """Agent should exit after max_cycles when opcua_enabled=True."""
    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    runner_patch, site_patch, mock_runner = _mock_health_server()

    with (
        patch("app.opcua_agent.main.get_settings") as mock_settings,
        patch("app.opcua_agent.main.create_async_engine", return_value=mock_engine),
        runner_patch,
        site_patch,
    ):
        mock_settings.return_value.opcua_enabled = True
        mock_settings.return_value.database_url = "postgresql+asyncpg://x@localhost/x"
        mock_settings.return_value.database_pool_size = 5
        mock_settings.return_value.database_max_overflow = 10
        mock_settings.return_value.database_pool_timeout = 30
        mock_settings.return_value.debug = False
        mock_settings.return_value.opcua_agent_poll_interval_seconds = 1
        mock_settings.return_value.opcua_max_connections_per_tenant = 5

        from app.opcua_agent.main import run_agent

        await run_agent(max_cycles=2)

    mock_engine.dispose.assert_awaited_once()
    mock_runner.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_disposes_engine_on_exception() -> None:
    """Engine must be disposed even if an exception occurs in the poll loop."""
    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    runner_patch, site_patch, mock_runner = _mock_health_server()

    with (
        patch("app.opcua_agent.main.get_settings") as mock_settings,
        patch("app.opcua_agent.main.create_async_engine", return_value=mock_engine),
        patch(
            "app.opcua_agent.main._sync_subscriptions",
            side_effect=RuntimeError("boom"),
        ),
        runner_patch,
        site_patch,
    ):
        mock_settings.return_value.opcua_enabled = True
        mock_settings.return_value.database_url = "postgresql+asyncpg://x@localhost/x"
        mock_settings.return_value.database_pool_size = 5
        mock_settings.return_value.database_max_overflow = 10
        mock_settings.return_value.database_pool_timeout = 30
        mock_settings.return_value.debug = False
        mock_settings.return_value.opcua_agent_poll_interval_seconds = 1
        mock_settings.return_value.opcua_max_connections_per_tenant = 5

        from app.opcua_agent.main import run_agent

        # _sync_subscriptions raises but it's caught by the except block,
        # so the agent continues and exits after max_cycles=1.
        # Engine is disposed in the finally block.
        await run_agent(max_cycles=1)

    mock_engine.dispose.assert_awaited_once()
    mock_runner.cleanup.assert_awaited_once()
