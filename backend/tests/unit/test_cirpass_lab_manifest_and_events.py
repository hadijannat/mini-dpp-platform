"""Unit tests for CIRPASS lab manifest and telemetry flows."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import app.modules.cirpass.service as cirpass_service_module
from app.modules.cirpass.schemas import CirpassLabEventRequest
from app.modules.cirpass.service import (
    CirpassLabService,
    CirpassRateLimitError,
    CirpassSessionError,
    CirpassValidationError,
)
from app.modules.lab.router import _RUNTIME_STATE, get_lab_status, reset_lab_state, seed_lab_state


class _FakeResult:
    def scalar_one_or_none(self) -> None:
        return None


class _FakeTelemetrySession:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def execute(self, _statement: object) -> _FakeResult:
        return _FakeResult()

    def add(self, row: Any) -> None:
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(UTC)
        self.events.append(row)

    async def flush(self) -> None:  # pragma: no cover - no-op for fake session
        return None


@pytest.mark.asyncio
async def test_manifest_latest_and_version_pinning() -> None:
    service = CirpassLabService(_FakeTelemetrySession())  # type: ignore[arg-type]

    latest = await service.get_lab_manifest_latest()
    pinned = await service.get_lab_manifest_version("v1.0.0")

    assert latest.manifest_version == "v1.0.0"
    assert pinned.manifest_version == "v1.0.0"
    assert latest.stories[0].id == pinned.stories[0].id

    with pytest.raises(CirpassValidationError):
        await service.get_lab_manifest_version("v9.9.9")


@pytest.mark.asyncio
async def test_telemetry_accepts_valid_payload_and_rejects_tampered_token() -> None:
    cirpass_service_module._sid_telemetry_window.clear()
    cirpass_service_module._ip_telemetry_window.clear()

    fake_db = _FakeTelemetrySession()
    service = CirpassLabService(fake_db)  # type: ignore[arg-type]
    session = await service.create_session(user_agent="TelemetryAgent")

    payload = CirpassLabEventRequest(
        session_token=session.session_token,
        story_id="core-loop-v3_1",
        step_id="create-passport",
        event_type="step_view",
        mode="mock",
        variant="happy",
        result="info",
        metadata={
            "source": "unit-test",
            "email": "hidden@example.com",
            "debug_token": "secret-token",
            "nested": {"safe": "ok", "ip_address": "10.0.0.1"},
        },
    )

    accepted = await service.record_lab_event(
        payload,
        user_agent="TelemetryAgent",
        client_ip="10.10.10.1",
    )

    assert accepted.accepted is True
    assert len(fake_db.events) == 1
    assert fake_db.events[0].metadata_json == {"source": "unit-test", "nested": {"safe": "ok"}}

    with pytest.raises(CirpassSessionError):
        await service.record_lab_event(
            payload.model_copy(update={"session_token": f"{session.session_token}x"}),
            user_agent="TelemetryAgent",
            client_ip="10.10.10.1",
        )


@pytest.mark.asyncio
async def test_telemetry_rate_limit_enforced() -> None:
    cirpass_service_module._sid_telemetry_window.clear()
    cirpass_service_module._ip_telemetry_window.clear()

    fake_db = _FakeTelemetrySession()
    service = CirpassLabService(fake_db)  # type: ignore[arg-type]
    session = await service.create_session(user_agent="TelemetryAgent")

    original_sid_limit = cirpass_service_module._TELEMETRY_HOURLY_LIMIT_PER_SID
    original_ip_limit = cirpass_service_module._TELEMETRY_DAILY_LIMIT_PER_IP
    cirpass_service_module._TELEMETRY_HOURLY_LIMIT_PER_SID = 1
    cirpass_service_module._TELEMETRY_DAILY_LIMIT_PER_IP = 5

    try:
        payload = CirpassLabEventRequest(
            session_token=session.session_token,
            story_id="core-loop-v3_1",
            step_id="create-passport",
            event_type="step_submit",
            mode="mock",
            variant="happy",
            result="success",
            latency_ms=123,
        )

        await service.record_lab_event(
            payload,
            user_agent="TelemetryAgent",
            client_ip="10.10.10.2",
        )

        with pytest.raises(CirpassRateLimitError):
            await service.record_lab_event(
                payload,
                user_agent="TelemetryAgent",
                client_ip="10.10.10.2",
            )
    finally:
        cirpass_service_module._TELEMETRY_HOURLY_LIMIT_PER_SID = original_sid_limit
        cirpass_service_module._TELEMETRY_DAILY_LIMIT_PER_IP = original_ip_limit


@pytest.mark.asyncio
async def test_lab_reset_seed_and_status_idempotent() -> None:
    before = _RUNTIME_STATE.reset_count

    reset = await reset_lab_state(user=SimpleNamespace())
    assert reset.tenant == "lab"
    assert reset.reset_count == before + 1

    seeded_once = await seed_lab_state(user=SimpleNamespace(), scenario="core-loop-v3_1")
    seeded_twice = await seed_lab_state(user=SimpleNamespace(), scenario="core-loop-v3_1")

    assert seeded_once.dataset_hash == seeded_twice.dataset_hash
    assert seeded_once.scenario == seeded_twice.scenario == "core-loop-v3_1"

    status = await get_lab_status(user=SimpleNamespace())
    assert status.tenant == "lab"
    assert status.scenario == "core-loop-v3_1"
