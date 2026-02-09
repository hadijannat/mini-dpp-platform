"""Shared IDTA semantic registry accessors.

Loads semantic IDs, ESPR category mappings, and support status metadata
from a single repository-level JSON file used by backend and frontend.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

SupportStatus = Literal["supported", "experimental", "unavailable"]

_REGISTRY_RELATIVE_PATH = Path("shared/idta_semantic_registry.json")


@lru_cache(maxsize=1)
def load_semantic_registry() -> dict[str, Any]:
    """Load and cache the semantic registry JSON document."""
    repo_root = Path(__file__).resolve().parents[3]
    registry_path = repo_root / _REGISTRY_RELATIVE_PATH
    with registry_path.open("r", encoding="utf-8") as handle:
        return cast(dict[str, Any], json.load(handle))


def get_template_registry_entry(template_key: str) -> dict[str, Any] | None:
    templates = load_semantic_registry().get("templates", {})
    if not isinstance(templates, dict):
        return None
    entry = templates.get(template_key)
    return entry if isinstance(entry, dict) else None


def get_template_semantic_id(template_key: str) -> str | None:
    entry = get_template_registry_entry(template_key)
    if not entry:
        return None
    semantic_id = entry.get("semantic_id")
    if isinstance(semantic_id, str) and semantic_id:
        return semantic_id
    return None


def get_template_support_status(template_key: str) -> SupportStatus:
    entry = get_template_registry_entry(template_key) or {}
    status = entry.get("support_status")
    if status in {"supported", "experimental", "unavailable"}:
        return cast(SupportStatus, status)
    return "supported"


def is_template_refresh_enabled(template_key: str) -> bool:
    entry = get_template_registry_entry(template_key) or {}
    return bool(entry.get("refresh_enabled", True))


def list_espr_tier_prefixes(tier: str) -> tuple[str, ...]:
    tiers = load_semantic_registry().get("espr_tier_prefixes", {})
    if not isinstance(tiers, dict):
        return ()
    prefixes = tiers.get(tier, [])
    if not isinstance(prefixes, list):
        return ()
    return tuple(prefix for prefix in prefixes if isinstance(prefix, str) and prefix)

