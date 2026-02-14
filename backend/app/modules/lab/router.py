"""Protected operations for deterministic CIRPASS lab sandbox state."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import Admin

router = APIRouter()


class LabResetResponse(BaseModel):
    tenant: str
    scenario: str
    dataset_hash: str
    reset_count: int
    status: str


class LabSeedResponse(BaseModel):
    tenant: str
    scenario: str
    dataset_hash: str
    seeded_at: str
    status: str


class LabStatusResponse(BaseModel):
    tenant: str
    scenario: str
    dataset_hash: str
    reset_count: int
    status: str
    live_mode_enabled: bool


@dataclass
class _LabRuntimeState:
    scenario: str = "baseline"
    reset_count: int = 0


_RUNTIME_STATE = _LabRuntimeState()


def _compute_dataset_hash(scenario: str) -> str:
    normalized = scenario.strip() or "baseline"
    return hashlib.sha256(f"lab::{normalized}".encode()).hexdigest()


@router.post("/reset", response_model=LabResetResponse)
async def reset_lab_state(user: Admin) -> LabResetResponse:
    """Reset lab tenant fixtures to deterministic baseline (admin only)."""
    del user

    _RUNTIME_STATE.scenario = "baseline"
    _RUNTIME_STATE.reset_count += 1

    return LabResetResponse(
        tenant="lab",
        scenario=_RUNTIME_STATE.scenario,
        dataset_hash=_compute_dataset_hash(_RUNTIME_STATE.scenario),
        reset_count=_RUNTIME_STATE.reset_count,
        status="ok",
    )


@router.post("/seed", response_model=LabSeedResponse)
async def seed_lab_state(
    user: Admin,
    scenario: str = Query(default="core-loop-v3_1", min_length=1, max_length=64),
) -> LabSeedResponse:
    """Seed deterministic fixtures required by a specific scenario (admin only)."""
    del user

    selected = scenario.strip()
    _RUNTIME_STATE.scenario = selected

    return LabSeedResponse(
        tenant="lab",
        scenario=selected,
        dataset_hash=_compute_dataset_hash(selected),
        seeded_at=datetime.now(UTC).isoformat(),
        status="ok",
    )


@router.get("/status", response_model=LabStatusResponse)
async def get_lab_status(user: Admin) -> LabStatusResponse:
    """Inspect current deterministic sandbox state for live-mode readiness."""
    del user

    settings = get_settings()
    return LabStatusResponse(
        tenant="lab",
        scenario=_RUNTIME_STATE.scenario,
        dataset_hash=_compute_dataset_hash(_RUNTIME_STATE.scenario),
        reset_count=_RUNTIME_STATE.reset_count,
        status="ready",
        live_mode_enabled=settings.cirpass_lab_live_mode_enabled,
    )
