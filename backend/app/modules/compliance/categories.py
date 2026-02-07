"""Auto-detect product category from AAS environment semantic IDs."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Map semantic ID prefixes to product categories.
# Order matters: first match wins, so more specific prefixes come first.
_SEMANTIC_ID_TO_CATEGORY: list[tuple[str, str]] = [
    # Battery Passport (IDTA 02035)
    ("https://admin-shell.io/idta/BatteryPassport/", "battery"),
    # Textile — no IDTA standard yet, use placeholder semantic IDs
    ("https://admin-shell.io/idta/TextilePassport/", "textile"),
    ("https://admin-shell.io/espr/textile/", "textile"),
    # Electronics — no IDTA standard yet, use placeholder semantic IDs
    ("https://admin-shell.io/idta/ElectronicPassport/", "electronic"),
    ("https://admin-shell.io/espr/electronic/", "electronic"),
]


def detect_category(aas_env: dict[str, Any]) -> str | None:
    """Auto-detect product category from semantic IDs found in the AAS environment.

    Scans all submodel semanticId values and returns the first matching category.
    Returns None if no known category can be determined.
    """
    submodels = aas_env.get("submodels")
    if not isinstance(submodels, list):
        return None

    for submodel in submodels:
        if not isinstance(submodel, dict):
            continue
        semantic_id = _extract_semantic_id(submodel)
        if not semantic_id:
            continue
        for prefix, category in _SEMANTIC_ID_TO_CATEGORY:
            if semantic_id.startswith(prefix):
                logger.debug(
                    "category_detected",
                    category=category,
                    semantic_id=semantic_id,
                )
                return category

    return None


def _extract_semantic_id(submodel: dict[str, Any]) -> str | None:
    """Extract the first semantic ID value from a submodel dict."""
    sem_id = submodel.get("semanticId")
    if not isinstance(sem_id, dict):
        return None
    keys = sem_id.get("keys")
    if not isinstance(keys, list) or not keys:
        return None
    first_key = keys[0]
    if not isinstance(first_key, dict):
        return None
    value = first_key.get("value")
    return str(value) if value else None
