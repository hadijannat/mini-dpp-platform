"""Canonicalization helpers for stable cross-platform hashing/signing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import rfc8785

CANONICALIZATION_RFC8785 = "rfc8785"
CANONICALIZATION_LEGACY_JSON_V1 = "legacy-json-v1"
SHA256_ALGORITHM = "sha-256"


def canonicalize_jcs_bytes(data: Any) -> bytes:
    """Return RFC 8785 (JCS) canonical bytes."""
    canonical = rfc8785.dumps(data)
    if isinstance(canonical, bytes):
        return canonical
    return str(canonical).encode("utf-8")


def sha256_hex_jcs(data: Any) -> str:
    """Compute SHA-256 hex digest over RFC 8785 canonical bytes."""
    return hashlib.sha256(canonicalize_jcs_bytes(data)).hexdigest()


def canonicalize_legacy_json_v1_bytes(
    data: Any,
    *,
    default_to_str: bool = False,
    ensure_ascii: bool = True,
) -> bytes:
    """Return legacy deterministic JSON bytes used before RFC 8785 migration."""
    kwargs: dict[str, Any] = {
        "sort_keys": True,
        "separators": (",", ":"),
        "ensure_ascii": ensure_ascii,
    }
    if default_to_str:
        kwargs["default"] = str
    return json.dumps(data, **kwargs).encode("utf-8")


def sha256_hex_for_canonicalization(
    data: Any,
    *,
    canonicalization: str,
    legacy_default_to_str: bool = False,
    legacy_ensure_ascii: bool = True,
) -> str:
    """Compute SHA-256 hex digest for the selected canonicalization mode."""
    if canonicalization == CANONICALIZATION_RFC8785:
        canonical = canonicalize_jcs_bytes(data)
    elif canonicalization == CANONICALIZATION_LEGACY_JSON_V1:
        canonical = canonicalize_legacy_json_v1_bytes(
            data,
            default_to_str=legacy_default_to_str,
            ensure_ascii=legacy_ensure_ascii,
        )
    else:
        raise ValueError(f"Unsupported canonicalization mode: {canonicalization}")
    return hashlib.sha256(canonical).hexdigest()
