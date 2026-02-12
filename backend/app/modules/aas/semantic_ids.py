"""Utilities for extracting and normalizing semantic IDs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from basyx.aas import model


def normalize_semantic_id(value: str | None) -> str | None:
    """Normalize semantic IDs for deterministic comparisons."""
    if not value:
        return None
    normalized = value.strip().rstrip("/").lower()
    return normalized or None


def reference_key_values(reference: model.Reference | None) -> list[str]:
    """Return all key values from a BaSyx reference."""
    if reference is None:
        return []
    keys: Iterable[Any] | None = getattr(reference, "keys", None)
    if keys is None:
        keys = getattr(reference, "key", None)
    if not keys:
        return []
    values: list[str] = []
    for key in keys:
        raw = getattr(key, "value", None)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            values.append(value)
    return values


def extract_semantic_ids(payload: dict[str, Any]) -> list[str]:
    """Extract semantic ID key values from AAS JSON payloads."""
    semantic_id = payload.get("semanticId")
    if not isinstance(semantic_id, dict):
        return []
    keys = semantic_id.get("keys")
    if not isinstance(keys, list):
        return []
    values: list[str] = []
    for key in keys:
        if not isinstance(key, dict):
            continue
        raw = key.get("value")
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            values.append(value)
    return values


def extract_normalized_semantic_ids(payload: dict[str, Any]) -> list[str]:
    """Extract and normalize semantic IDs from AAS JSON payloads."""
    normalized: list[str] = []
    seen: set[str] = set()
    for semantic_id in extract_semantic_ids(payload):
        value = normalize_semantic_id(semantic_id)
        if value and value not in seen:
            seen.add(value)
            normalized.append(value)
    return normalized
