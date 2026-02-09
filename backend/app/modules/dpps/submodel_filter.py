"""ESPR tiered access control for submodel visibility.

Each ESPR tier defines which AAS submodel semantic IDs the tier
can access. The mapping is based on semantic IDs because that's
how IDTA templates are identified.
"""

from __future__ import annotations

import copy
from typing import Any

from app.modules.semantic_registry import list_espr_tier_prefixes

# Semantic ID prefixes for tier-based visibility sourced from shared registry.
CONSUMER_SUBMODELS: frozenset[str] = frozenset(list_espr_tier_prefixes("consumer"))
RECYCLER_SUBMODELS: frozenset[str] = frozenset(list_espr_tier_prefixes("recycler"))

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
    *,
    in_place: bool = False,
) -> dict[str, Any]:
    """Filter an AAS environment based on the caller's ESPR tier.

    Anonymous/unauthenticated callers (``espr_tier=None``) default to the
    ``"consumer"`` tier (deny-by-default).  ``"manufacturer"`` and
    ``"market_surveillance_authority"`` tiers receive the full environment.
    All other tiers are filtered by semantic ID prefix matching.

    Args:
        in_place: If True, mutate ``aas_env`` directly instead of deep-copying.
            Use when the caller already owns a mutable copy.
    """
    if not espr_tier or not espr_tier.strip():
        espr_tier = "consumer"  # deny-by-default for anonymous access

    if espr_tier not in ESPR_TIER_SUBMODEL_MAP:
        # Unknown tier gets no submodel access (deny-by-default)
        allowed: frozenset[str] | None = frozenset()
    else:
        allowed = ESPR_TIER_SUBMODEL_MAP[espr_tier]

    if allowed is None:
        return aas_env  # Full access tiers (authority/manufacturer)

    target = aas_env if in_place else copy.deepcopy(aas_env)
    target["submodels"] = [
        sm for sm in target.get("submodels", []) if _submodel_matches_tier(sm, allowed)
    ]
    return target


def _submodel_matches_tier(
    submodel: dict[str, Any],
    allowed_prefixes: frozenset[str],
) -> bool:
    """Check if a submodel's semantic ID matches any allowed prefix."""
    semantic_id = _extract_semantic_id(submodel)
    if not semantic_id:
        return False  # No semantic ID = deny-by-default
    return any(semantic_id.startswith(prefix) for prefix in allowed_prefixes)


def _extract_semantic_id(submodel: dict[str, Any]) -> str:
    """Extract the semantic ID string from a submodel dict."""
    sem_id = submodel.get("semanticId", {})
    keys = sem_id.get("keys", [])
    if keys:
        return str(keys[0].get("value", ""))
    return ""
