"""Electronics-specific compliance validator (ESPR Electronics Regulation)."""

from __future__ import annotations

from app.modules.compliance.validators.base import CategoryValidator


class ElectronicValidator(CategoryValidator):
    """Validates electronics DPPs against ESPR electronics regulation rules.

    Uses the generic rule engine from the base class. Extend ``validate``
    to add electronics-specific cross-field checks in the future.
    """

    category: str = "electronic"
