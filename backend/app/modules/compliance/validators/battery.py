"""Battery-specific compliance validator (EU Battery Regulation 2023/1542)."""

from __future__ import annotations

from app.modules.compliance.validators.base import CategoryValidator


class BatteryValidator(CategoryValidator):
    """Validates battery DPPs against EU Battery Regulation rules.

    Uses the generic rule engine from the base class. Extend ``validate``
    to add battery-specific cross-field checks in the future.
    """

    category: str = "battery"
