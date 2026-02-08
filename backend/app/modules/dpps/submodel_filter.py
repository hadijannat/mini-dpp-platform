"""ESPR tiered access control for submodel visibility.

Each ESPR tier defines which AAS submodel semantic IDs the tier
can access. The mapping is based on semantic IDs because that's
how IDTA templates are identified.
"""

from __future__ import annotations

import copy
from typing import Any

# Semantic ID prefixes for tier-based visibility.
# These match the IDTA DPP4.0 template semantic IDs.
CONSUMER_SUBMODELS: frozenset[str] = frozenset(
    {
        "https://admin-shell.io/zvei/nameplate",  # DigitalNameplate
        "https://admin-shell.io/idta/TechnicalData",  # TechnicalData
        "https://admin-shell.io/idta/CarbonFootprint",  # (basic view)
    }
)

RECYCLER_SUBMODELS: frozenset[str] = CONSUMER_SUBMODELS | frozenset(
    {
        "https://admin-shell.io/idta/CarbonFootprint",  # Full CarbonFootprint
    }
)

AUTHORITY_SUBMODELS: frozenset[str] | None = None  # All visible

ESPR_TIER_SUBMODEL_MAP: dict[str, frozenset[str] | None] = {
    "consumer": CONSUMER_SUBMODELS,
    "recycler": RECYCLER_SUBMODELS,
    "market_surveillance_authority": None,  # All
    "manufacturer": None,  # All (with CRUD)
}


def filter_aas_env_by_espr_tier(
    aas_env: dict[str, Any],
    espr_tier: str | None,
) -> dict[str, Any]:
    """Filter an AAS environment based on the caller's ESPR tier.

    If espr_tier is None or "manufacturer" or "market_surveillance_authority",
    returns the full environment. Otherwise, filters submodels
    based on semantic ID prefix matching against the tier's allowed set.
    """
    if espr_tier is None:
        return aas_env  # No tier = no filtering (backwards compatible)

    allowed = ESPR_TIER_SUBMODEL_MAP.get(espr_tier)
    if allowed is None:
        return aas_env  # Full access tiers

    filtered = copy.deepcopy(aas_env)
    filtered["submodels"] = [
        sm for sm in filtered.get("submodels", []) if _submodel_matches_tier(sm, allowed)
    ]
    return filtered


def _submodel_matches_tier(
    submodel: dict[str, Any],
    allowed_prefixes: frozenset[str],
) -> bool:
    """Check if a submodel's semantic ID matches any allowed prefix."""
    semantic_id = _extract_semantic_id(submodel)
    if not semantic_id:
        return True  # No semantic ID = visible to all (defensive default)
    return any(semantic_id.startswith(prefix) for prefix in allowed_prefixes)


def _extract_semantic_id(submodel: dict[str, Any]) -> str:
    """Extract the semantic ID string from a submodel dict."""
    sem_id = submodel.get("semanticId", {})
    keys = sem_id.get("keys", [])
    if keys:
        return str(keys[0].get("value", ""))
    return ""
