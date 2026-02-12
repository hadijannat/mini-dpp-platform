"""
Database-backed settings service.
"""

from __future__ import annotations

import json
from inspect import isawaitable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlatformSetting


class SettingsService:
    """Service for reading/writing platform settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_setting(self, key: str) -> str | None:
        result = await self._session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if isawaitable(setting):
            setting = await setting
        value = getattr(setting, "value", None) if setting else None
        return value if isinstance(value, str) else None

    async def get_setting_bool(self, key: str, *, default: bool = False) -> bool:
        """Read a boolean setting with permissive string parsing."""
        raw = await self.get_setting(key)
        if raw is None:
            return default
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    async def get_setting_json(self, key: str) -> dict[str, Any] | None:
        """Read a JSON object setting; returns None for missing/invalid values."""
        raw = await self.get_setting(key)
        if raw is None:
            return None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    async def set_setting(
        self, key: str, value: str, updated_by: str | None = None
    ) -> PlatformSetting:
        result = await self._session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if isawaitable(setting):
            setting = await setting
        if setting is None:
            setting = PlatformSetting(
                key=key,
                value=value,
                updated_by=updated_by,
            )
            self._session.add(setting)
        else:
            setting.value = value
            setting.updated_by = updated_by
        await self._session.flush()
        return setting

    async def set_setting_bool(
        self, key: str, value: bool, updated_by: str | None = None
    ) -> PlatformSetting:
        """Persist a boolean setting as a normalized string."""
        return await self.set_setting(key, "true" if value else "false", updated_by=updated_by)

    async def set_setting_json(
        self, key: str, value: dict[str, Any], updated_by: str | None = None
    ) -> PlatformSetting:
        """Persist a JSON object setting."""
        return await self.set_setting(
            key,
            json.dumps(value, separators=(",", ":"), sort_keys=True),
            updated_by=updated_by,
        )
