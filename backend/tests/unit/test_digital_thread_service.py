"""Tests for the digital_thread module — service, handlers, and schemas.

Covers:
- ThreadService.record_event / get_events / get_timeline
- record_lifecycle_event auto-emission handler
- Schema validation (ThreadEventCreate)
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import LifecyclePhase
from app.modules.digital_thread.handlers import (
    DEFAULT_ACTION_PHASE_MAP,
    record_lifecycle_event,
)
from app.modules.digital_thread.schemas import (
    EventQuery,
    ThreadEventCreate,
    ThreadEventResponse,
)
from app.modules.digital_thread.service import ThreadService

# ── Schema Validation ──────────────────────────────────────────────


class TestThreadEventCreateSchema:
    """Validates ThreadEventCreate Pydantic constraints."""

    def test_valid_minimal_event(self) -> None:
        event = ThreadEventCreate(
            phase=LifecyclePhase.DESIGN,
            event_type="dpp_created",
            source="platform",
        )
        assert event.phase == LifecyclePhase.DESIGN
        assert event.payload == {}
        assert event.parent_event_id is None

    def test_valid_full_event(self) -> None:
        parent_id = uuid4()
        event = ThreadEventCreate(
            phase=LifecyclePhase.MANUFACTURE,
            event_type="material_sourced",
            source="ERP-System",
            source_event_id="ERP-2024-001",
            payload={"material": "steel", "weight_kg": 42.5},
            parent_event_id=parent_id,
        )
        assert event.source_event_id == "ERP-2024-001"
        assert event.parent_event_id == parent_id

    def test_rejects_empty_event_type(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="event_type"):
            ThreadEventCreate(
                phase=LifecyclePhase.DESIGN,
                event_type="",
                source="platform",
            )

    def test_rejects_empty_source(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="source"):
            ThreadEventCreate(
                phase=LifecyclePhase.DESIGN,
                event_type="dpp_created",
                source="",
            )

    def test_rejects_oversized_event_type(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="event_type"):
            ThreadEventCreate(
                phase=LifecyclePhase.DESIGN,
                event_type="x" * 101,
                source="platform",
            )


class TestEventQuerySchema:
    """Validates EventQuery constraints."""

    def test_defaults(self) -> None:
        q = EventQuery(dpp_id=uuid4())
        assert q.limit == 50
        assert q.offset == 0
        assert q.phase is None

    def test_limit_bounds(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EventQuery(dpp_id=uuid4(), limit=0)
        with pytest.raises(ValidationError):
            EventQuery(dpp_id=uuid4(), limit=501)


# ── Service Layer ──────────────────────────────────────────────────


def _mock_dpp(dpp_id=None, tenant_id=None):
    """Create a minimal mock DPP."""
    dpp = MagicMock()
    dpp.id = dpp_id or uuid4()
    dpp.tenant_id = tenant_id or uuid4()
    return dpp


def _mock_thread_event(
    *,
    dpp_id=None,
    tenant_id=None,
    phase=LifecyclePhase.DESIGN,
    event_type="dpp_created",
) -> MagicMock:
    """Create a mock ThreadEvent row."""
    row = MagicMock()
    row.id = uuid4()
    row.dpp_id = dpp_id or uuid4()
    row.tenant_id = tenant_id or uuid4()
    row.phase = phase
    row.event_type = event_type
    row.source = "platform"
    row.source_event_id = None
    row.payload = {}
    row.parent_event_id = None
    row.created_by_subject = "test-user"
    row.created_at = datetime.now(UTC)
    return row


class TestThreadServiceRecordEvent:
    """ThreadService.record_event tests."""

    @pytest.mark.asyncio()
    async def test_record_event_success(self) -> None:
        dpp_id = uuid4()
        tenant_id = uuid4()
        mock_dpp = _mock_dpp(dpp_id, tenant_id)

        session = AsyncMock()
        # _get_dpp returns a DPP
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_dpp
        session.execute.return_value = result_mock

        # flush produces a ThreadEvent-like object with model_validate compat
        async def side_effect_flush():
            pass

        session.flush = AsyncMock(side_effect=side_effect_flush)

        service = ThreadService(session)
        event = ThreadEventCreate(
            phase=LifecyclePhase.DESIGN,
            event_type="dpp_created",
            source="platform",
        )

        with patch.object(
            ThreadEventResponse,
            "model_validate",
            return_value=ThreadEventResponse(
                id=uuid4(),
                dpp_id=dpp_id,
                phase=LifecyclePhase.DESIGN,
                event_type="dpp_created",
                source="platform",
                created_by_subject="test-user",
                created_at=datetime.now(UTC),
            ),
        ):
            result = await service.record_event(dpp_id, tenant_id, event, "test-user")

        assert result.dpp_id == dpp_id
        assert result.event_type == "dpp_created"
        session.add.assert_called_once()

    @pytest.mark.asyncio()
    async def test_record_event_dpp_not_found_raises(self) -> None:
        dpp_id = uuid4()
        tenant_id = uuid4()

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute.return_value = result_mock

        service = ThreadService(session)
        event = ThreadEventCreate(
            phase=LifecyclePhase.DESIGN,
            event_type="dpp_created",
            source="platform",
        )

        with pytest.raises(ValueError, match="not found"):
            await service.record_event(dpp_id, tenant_id, event, "test-user")


class TestThreadServiceGetEvents:
    """ThreadService.get_events tests."""

    @pytest.mark.asyncio()
    async def test_get_events_returns_list(self) -> None:
        dpp_id = uuid4()
        tenant_id = uuid4()
        row = _mock_thread_event(dpp_id=dpp_id, tenant_id=tenant_id)

        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [row]
        session.execute.return_value = result_mock

        service = ThreadService(session)
        query = EventQuery(dpp_id=dpp_id, phase=LifecyclePhase.DESIGN)

        with patch.object(
            ThreadEventResponse,
            "model_validate",
            return_value=ThreadEventResponse(
                id=row.id,
                dpp_id=dpp_id,
                phase=LifecyclePhase.DESIGN,
                event_type="dpp_created",
                source="platform",
                created_by_subject="test-user",
                created_at=datetime.now(UTC),
            ),
        ):
            results = await service.get_events(tenant_id, query)

        assert len(results) == 1
        assert results[0].phase == LifecyclePhase.DESIGN

    @pytest.mark.asyncio()
    async def test_get_events_empty_when_no_matches(self) -> None:
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        service = ThreadService(session)
        query = EventQuery(dpp_id=uuid4())
        results = await service.get_events(uuid4(), query)
        assert results == []


# ── Auto-Emission Handler ──────────────────────────────────────────


class TestRecordLifecycleEvent:
    """Tests for the fire-and-forget auto-emission handler."""

    def test_action_phase_map_has_all_actions(self) -> None:
        assert set(DEFAULT_ACTION_PHASE_MAP.keys()) == {
            "create",
            "update",
            "publish",
            "archive",
        }

    def test_action_mappings_are_valid(self) -> None:
        for _action, (phase, event_type) in DEFAULT_ACTION_PHASE_MAP.items():
            assert isinstance(phase, LifecyclePhase)
            assert isinstance(event_type, str)
            assert len(event_type) > 0

    @pytest.mark.asyncio()
    async def test_noop_when_disabled(self) -> None:
        session = AsyncMock()
        with patch(
            "app.modules.digital_thread.handlers.get_settings",
            return_value=SimpleNamespace(
                digital_thread_enabled=False,
                digital_thread_auto_record=True,
            ),
        ):
            await record_lifecycle_event(session, uuid4(), uuid4(), "create", "user-1")
        # Session should not be touched
        session.begin_nested.assert_not_called()

    @pytest.mark.asyncio()
    async def test_noop_when_auto_record_disabled(self) -> None:
        session = AsyncMock()
        with patch(
            "app.modules.digital_thread.handlers.get_settings",
            return_value=SimpleNamespace(
                digital_thread_enabled=True,
                digital_thread_auto_record=False,
            ),
        ):
            await record_lifecycle_event(session, uuid4(), uuid4(), "publish", "user-1")
        session.begin_nested.assert_not_called()

    @pytest.mark.asyncio()
    async def test_noop_for_unknown_action(self) -> None:
        session = AsyncMock()
        with patch(
            "app.modules.digital_thread.handlers.get_settings",
            return_value=SimpleNamespace(
                digital_thread_enabled=True,
                digital_thread_auto_record=True,
            ),
        ):
            await record_lifecycle_event(session, uuid4(), uuid4(), "unknown_action", "user-1")
        session.begin_nested.assert_not_called()

    @pytest.mark.asyncio()
    async def test_swallows_exceptions(self) -> None:
        """Handler must never raise, even if the DB fails."""
        session = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        session.begin_nested.return_value = ctx

        with patch(
            "app.modules.digital_thread.handlers.get_settings",
            return_value=SimpleNamespace(
                digital_thread_enabled=True,
                digital_thread_auto_record=True,
            ),
        ):
            # Should not raise
            await record_lifecycle_event(session, uuid4(), uuid4(), "create", "user-1")
