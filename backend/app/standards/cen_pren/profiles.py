"""CEN prEN profile resolution and header helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class CENProfiles:
    """Resolved CEN profile versions for active standards workstreams."""

    enabled: bool
    profile_18219: str
    profile_18220: str
    profile_18222: str


def get_cen_profiles(settings: Settings | None = None) -> CENProfiles:
    """Resolve CEN profile settings from runtime configuration."""
    cfg = settings or get_settings()
    return CENProfiles(
        enabled=cfg.cen_dpp_enabled,
        profile_18219=cfg.cen_profile_18219,
        profile_18220=cfg.cen_profile_18220,
        profile_18222=cfg.cen_profile_18222,
    )


def standards_profile_header(profiles: CENProfiles) -> str:
    """Serialize CEN profile versions for API response headers."""
    return f"CEN-{profiles.profile_18219};CEN-{profiles.profile_18220};CEN-{profiles.profile_18222}"
