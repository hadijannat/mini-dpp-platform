"""
Audit chain and event verification utilities.

Provides functions to verify the integrity of hash chains — both individual
events and full sequences. These are pure functions operating on dicts,
decoupled from the database layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.crypto.hash_chain import GENESIS_HASH, compute_event_hash


@dataclass
class ChainVerificationResult:
    """Result of verifying a hash chain.

    Attributes
    ----------
    is_valid:
        ``True`` if the entire chain is intact.
    verified_count:
        Number of events successfully verified.
    first_break_at:
        Zero-based index where the chain first broke, or ``None``.
    errors:
        Human-readable descriptions of integrity violations.
    """

    is_valid: bool = True
    verified_count: int = 0
    first_break_at: int | None = None
    errors: list[str] = field(default_factory=list)


def _extract_event_data(event: dict[str, Any]) -> dict[str, Any]:
    """Extract the hashable payload from an event dict.

    Strips chain-metadata fields (``event_hash``, ``prev_event_hash``,
    ``chain_sequence``) so that only the original event data is hashed.
    """
    exclude = {"event_hash", "prev_event_hash", "chain_sequence"}
    return {k: v for k, v in event.items() if k not in exclude}


def verify_event(event: dict[str, Any], prev_hash: str | None) -> bool:
    """Verify a single event's hash against its claimed predecessor.

    Parameters
    ----------
    event:
        Event dict containing at least ``event_hash`` and the original
        event fields.
    prev_hash:
        The hash of the previous event, or ``None`` for the genesis event.

    Returns
    -------
    bool
        ``True`` if the stored ``event_hash`` matches the recomputed hash.
    """
    stored_hash = event.get("event_hash")
    if stored_hash is None:
        return False

    effective_prev = prev_hash if prev_hash is not None else GENESIS_HASH
    event_data = _extract_event_data(event)
    expected = compute_event_hash(event_data, effective_prev)
    return bool(stored_hash == expected)


def verify_hash_chain(
    events: list[dict[str, Any]],
) -> ChainVerificationResult:
    """Verify the integrity of a sequence of chained audit events.

    Events must be ordered by ``chain_sequence`` (ascending). Each event's
    ``event_hash`` is recomputed from its data and the previous event's
    hash, then compared to the stored value.

    Parameters
    ----------
    events:
        Ordered list of event dicts. Each must contain ``event_hash``
        and ``prev_event_hash`` fields.

    Returns
    -------
    ChainVerificationResult
        Detailed verification outcome.
    """
    result = ChainVerificationResult()

    if not events:
        return result

    for i, event in enumerate(events):
        stored_hash = event.get("event_hash")
        stored_prev = event.get("prev_event_hash")

        if stored_hash is None:
            result.is_valid = False
            result.first_break_at = i
            result.errors.append(
                f"Event at index {i}: missing event_hash"
            )
            break

        # Determine expected prev_hash
        expected_prev = (
            GENESIS_HASH
            if i == 0
            else events[i - 1].get("event_hash", GENESIS_HASH)
        )

        # Check prev_hash linkage
        if stored_prev is not None and stored_prev != expected_prev:
            result.is_valid = False
            if result.first_break_at is None:
                result.first_break_at = i
            result.errors.append(
                f"Event at index {i}: prev_event_hash mismatch "
                f"(stored={stored_prev!r}, expected={expected_prev!r})"
            )
            break

        # Recompute and verify
        event_data = _extract_event_data(event)
        recomputed = compute_event_hash(event_data, expected_prev)

        if recomputed != stored_hash:
            result.is_valid = False
            if result.first_break_at is None:
                result.first_break_at = i
            result.errors.append(
                f"Event at index {i}: hash mismatch "
                f"(stored={stored_hash!r}, recomputed={recomputed!r})"
            )
            break

        result.verified_count += 1

    return result
