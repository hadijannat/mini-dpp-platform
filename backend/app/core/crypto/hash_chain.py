"""
SHA-256 hash chaining for sequential audit event integrity.

Each event hash is computed as ``SHA256(canonical_json(event_data) + prev_hash)``,
creating a tamper-evident chain where modifying any event invalidates all
subsequent hashes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: dict[str, Any]) -> bytes:
    """Produce deterministic JSON bytes from a dict.

    Guarantees identical output for identical logical data regardless of
    insertion order by sorting keys recursively. Uses no whitespace and
    ensures ASCII encoding for reproducibility.

    Parameters
    ----------
    data:
        The dictionary to serialize.

    Returns
    -------
    bytes
        UTF-8 encoded canonical JSON.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def compute_event_hash(event_data: dict[str, Any], prev_hash: str) -> str:
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
    payload = canonical_json(event_data)
    hasher = hashlib.sha256()
    hasher.update(payload)
    hasher.update(prev_hash.encode("utf-8"))
    return hasher.hexdigest()


# Convenience constant for the genesis (first) event in a chain.
GENESIS_HASH: str = "0" * 64
