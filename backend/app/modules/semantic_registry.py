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


def _normalize_semantic_id(value: str) -> str:
    return value.strip().rstrip("/").lower()


def list_dropin_bindings() -> dict[str, list[dict[str, Any]]]:
    """Return registry-configured drop-in bindings keyed by semantic ID."""
    raw = load_semantic_registry().get("dropin_bindings", {})
    if not isinstance(raw, dict):
        return {}

    bindings: dict[str, list[dict[str, Any]]] = {}
    for semantic_id, entries in raw.items():
        if not isinstance(semantic_id, str) or not semantic_id.strip():
            continue
        if not isinstance(entries, list):
            continue
        normalized_key = _normalize_semantic_id(semantic_id)
        normalized_entries = [entry for entry in entries if isinstance(entry, dict)]
        if normalized_entries:
            bindings[normalized_key] = normalized_entries
    return bindings


def get_dropin_bindings_for_semantic_id(semantic_id: str | None) -> tuple[dict[str, Any], ...]:
    """Return drop-in bindings registered for a semantic ID."""
    if not semantic_id:
        return ()
    normalized = _normalize_semantic_id(semantic_id)
    entries = list_dropin_bindings().get(normalized, [])
    return tuple(entries)
