"""Textile-specific compliance validator (ESPR Textile Regulation)."""

from __future__ import annotations

from app.modules.compliance.validators.base import CategoryValidator


class TextileValidator(CategoryValidator):
    """Validates textile DPPs against ESPR textile regulation rules.

    Uses the generic rule engine from the base class. Extend ``validate``
    to add textile-specific cross-field checks in the future.
    """

    category: str = "textile"
