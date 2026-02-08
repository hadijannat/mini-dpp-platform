"""Unit tests for EPCIS auto-emission handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.epcis.handlers import record_epcis_lifecycle_event

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TENANT_ID = uuid4()
_DPP_ID = uuid4()


def _make_session(*, should_fail: bool = False) -> AsyncMock:
    """Build a mock AsyncSession with begin_nested context manager."""
    session = AsyncMock()
    if should_fail:

        @asynccontextmanager
        async def _failing_nested() -> Any:
            raise RuntimeError("DB error")
            yield  # pragma: no cover

        session.begin_nested = _failing_nested
    else:

        @asynccontextmanager
        async def _ok_nested() -> Any:
            yield

        session.begin_nested = _ok_nested
    return session


# ---------------------------------------------------------------------------
# Tests: record_epcis_lifecycle_event
# ---------------------------------------------------------------------------


class TestRecordEPCISLifecycleEvent:
    @pytest.mark.asyncio
    async def test_disabled_epcis_does_nothing(self) -> None:
        """When epcis_enabled is False, no event is recorded."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = False
            mock_settings.return_value.epcis_auto_record = True
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="create",
                created_by="user-1",
            )
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_auto_record_does_nothing(self) -> None:
        """When epcis_auto_record is False, no event is recorded."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = False
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="create",
                created_by="user-1",
            )
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_action_does_nothing(self) -> None:
        """An unmapped action should silently do nothing."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = True
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="unknown_action",
                created_by="user-1",
            )
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_action_records_event(self) -> None:
        """The 'create' action should record an EPCIS ObjectEvent."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = True
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="create",
                created_by="user-1",
            )
        session.add.assert_called_once()
        event = session.add.call_args[0][0]
        assert event.biz_step == "commissioning"
        assert event.disposition == "active"
        assert event.action == "ADD"

    @pytest.mark.asyncio
    async def test_publish_action_records_event(self) -> None:
        """The 'publish' action should record an OBSERVE event."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = True
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="publish",
                created_by="user-1",
            )
        session.add.assert_called_once()
        event = session.add.call_args[0][0]
        assert event.biz_step == "inspecting"
        assert event.disposition == "conformant"
        assert event.action == "OBSERVE"

    @pytest.mark.asyncio
    async def test_archive_action_records_event(self) -> None:
        """The 'archive' action should record a DELETE event."""
        session = _make_session()
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = True
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="archive",
                created_by="user-1",
            )
        session.add.assert_called_once()
        event = session.add.call_args[0][0]
        assert event.biz_step == "decommissioning"
        assert event.disposition == "inactive"
        assert event.action == "DELETE"

    @pytest.mark.asyncio
    async def test_db_error_swallowed(self) -> None:
        """Database errors should be swallowed, never propagated to caller."""
        session = _make_session(should_fail=True)
        with patch("app.modules.epcis.handlers.get_settings") as mock_settings:
            mock_settings.return_value.epcis_enabled = True
            mock_settings.return_value.epcis_auto_record = True
            # Should NOT raise
            await record_epcis_lifecycle_event(
                session=session,
                dpp_id=_DPP_ID,
                tenant_id=_TENANT_ID,
                action="create",
                created_by="user-1",
            )
