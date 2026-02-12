"""Unit tests for database-backed settings helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.settings_service import SettingsService


@pytest.mark.asyncio
async def test_get_setting_bool_parses_true_false() -> None:
    service = SettingsService(AsyncMock())
    service.get_setting = AsyncMock(side_effect=["true", "false", "unexpected", None])  # type: ignore[method-assign]

    assert await service.get_setting_bool("k1", default=False) is True
    assert await service.get_setting_bool("k2", default=True) is False
    assert await service.get_setting_bool("k3", default=True) is True
    assert await service.get_setting_bool("k4", default=False) is False


@pytest.mark.asyncio
async def test_get_setting_json_parses_dict_only() -> None:
    service = SettingsService(AsyncMock())
    service.get_setting = AsyncMock(side_effect=['{"a":1}', '["a"]', "{bad", None])  # type: ignore[method-assign]

    assert await service.get_setting_json("k1") == {"a": 1}
    assert await service.get_setting_json("k2") is None
    assert await service.get_setting_json("k3") is None
    assert await service.get_setting_json("k4") is None
