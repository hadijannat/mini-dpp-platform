"""
Database-backed settings service.
"""

from __future__ import annotations

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
        return setting.value if setting else None

    async def set_setting(self, key: str, value: str, updated_by: str | None = None) -> PlatformSetting:
        result = await self._session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
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
