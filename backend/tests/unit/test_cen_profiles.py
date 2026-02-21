"""Tests for CEN profile helpers."""

from __future__ import annotations

from app.standards.cen_pren.profiles import CENProfiles, standards_profile_header


def test_standards_profile_header_serialization() -> None:
    profiles = CENProfiles(
        enabled=True,
        profile_18219="prEN18219:2025-07",
        profile_18220="prEN18220:2025-07",
        profile_18222="prEN18222:2025-07",
    )
    assert standards_profile_header(profiles) == (
        "CEN-prEN18219:2025-07;CEN-prEN18220:2025-07;CEN-prEN18222:2025-07"
    )
