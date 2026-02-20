"""
SHA-256 hash chaining for sequential audit event integrity.

Each event hash is computed as ``SHA256(canonical_json(event_data) + prev_hash)``,
creating a tamper-evident chain where modifying any event invalidates all
subsequent hashes.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.core.crypto.canonicalization import (
    CANONICALIZATION_LEGACY_JSON_V1,
    CANONICALIZATION_RFC8785,
    SHA256_ALGORITHM,
    canonicalize_jcs_bytes,
    canonicalize_legacy_json_v1_bytes,
)

HASH_CANONICALIZATION_RFC8785 = CANONICALIZATION_RFC8785
HASH_CANONICALIZATION_LEGACY_JSON_V1 = CANONICALIZATION_LEGACY_JSON_V1
HASH_ALGORITHM_SHA256 = SHA256_ALGORITHM


def canonical_json(
    data: dict[str, Any],
    *,
    canonicalization: str = HASH_CANONICALIZATION_RFC8785,
) -> bytes:
    """Produce deterministic JSON bytes from a dict.

    RFC 8785 is used for new writes. Legacy verification can still use
    ``legacy-json-v1`` for hashes generated before canonicalization hardening.

    Parameters
    ----------
    data:
        The dictionary to serialize.

    Returns
    -------
    bytes
        UTF-8 encoded canonical JSON.
    """
    if canonicalization == HASH_CANONICALIZATION_RFC8785:
        return canonicalize_jcs_bytes(data)
    if canonicalization == HASH_CANONICALIZATION_LEGACY_JSON_V1:
        return canonicalize_legacy_json_v1_bytes(data, default_to_str=True, ensure_ascii=True)
    raise ValueError(f"Unsupported hash canonicalization: {canonicalization}")


def compute_event_hash(
    event_data: dict[str, Any],
    prev_hash: str,
    *,
    canonicalization: str = HASH_CANONICALIZATION_RFC8785,
    hash_algorithm: str = HASH_ALGORITHM_SHA256,
) -> str:
    """Compute the SHA-256 hash for an audit event in a chain.

    The hash covers both the event payload and the previous event's hash,
    creating a sequential integrity chain.

    Parameters
    ----------
    event_data:
        Dictionary of event fields to include in the hash.
    prev_hash:
        Hex-encoded SHA-256 hash of the previous event in the chain.
        Use ``"0" * 64`` (64 zeros) for the genesis event.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    if hash_algorithm != HASH_ALGORITHM_SHA256:
        raise ValueError(f"Unsupported hash algorithm: {hash_algorithm}")
    payload = canonical_json(event_data, canonicalization=canonicalization)
    hasher = hashlib.sha256()
    hasher.update(payload)
    hasher.update(prev_hash.encode("utf-8"))
    return hasher.hexdigest()


# Convenience constant for the genesis (first) event in a chain.
GENESIS_HASH: str = "0" * 64
