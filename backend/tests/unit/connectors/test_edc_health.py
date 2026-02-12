"""Unit tests for EDC health probe."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.connectors.edc.health import check_edc_health


@pytest.mark.asyncio
async def test_health_ok() -> None:
    client = MagicMock()
    client.check_health = AsyncMock(
        return_value={
            "componentResults": [{"component": "default", "isSystemHealthy": True}],
            "version": "0.7.3",
        }
    )

    result = await check_edc_health(client)

    assert result["status"] == "ok"
    assert result["edc_version"] == "0.7.3"


@pytest.mark.asyncio
async def test_health_error_from_edc() -> None:
    client = MagicMock()
    client.check_health = AsyncMock(
        return_value={
            "status": "error",
            "error_code": 503,
            "error_message": "Service unavailable",
        }
    )

    result = await check_edc_health(client)

    assert result["status"] == "error"
    assert result["error_code"] == 503


@pytest.mark.asyncio
async def test_health_404_uses_management_fallback() -> None:
    client = MagicMock()
    client.check_health = AsyncMock(
        return_value={
            "status": "error",
            "error_code": 404,
            "error_message": "Not found",
        }
    )
    client.get_asset = AsyncMock(return_value=None)

    result = await check_edc_health(client)

    assert result["status"] == "ok"
    client.get_asset.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_404_fallback_failure_returns_error() -> None:
    client = MagicMock()
    client.check_health = AsyncMock(
        return_value={
            "status": "error",
            "error_code": 404,
            "error_message": "Not found",
        }
    )
    client.get_asset = AsyncMock(side_effect=ConnectionError("unreachable"))

    result = await check_edc_health(client)

    assert result["status"] == "error"
    assert result["error_code"] == 404


@pytest.mark.asyncio
async def test_health_exception() -> None:
    client = MagicMock()
    client.check_health = AsyncMock(side_effect=ConnectionError("refused"))

    result = await check_edc_health(client)

    assert result["status"] == "error"
    assert "refused" in result["error_message"]
