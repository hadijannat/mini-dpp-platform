"""Tests for crypto verification module."""

from __future__ import annotations

from app.core.crypto.hash_chain import GENESIS_HASH, compute_event_hash
from app.core.crypto.verification import (
    ChainVerificationResult,
    verify_event,
    verify_hash_chain,
)


def _build_chain(events_data: list[dict[str, object]]) -> list[dict[str, object]]:
    """Build a valid chain of events with proper hashes."""
    chain: list[dict[str, object]] = []
    prev_hash = GENESIS_HASH
    for i, data in enumerate(events_data):
        event_hash = compute_event_hash(
            dict(data.items()),
            prev_hash,
        )
        chain.append(
            {
                **data,
                "event_hash": event_hash,
                "prev_event_hash": prev_hash,
                "chain_sequence": i,
            }
        )
        prev_hash = event_hash
    return chain


class TestVerifyEvent:
    """Tests for single event verification."""

    def test_valid_genesis_event(self) -> None:
        data = {"action": "create"}
        event_hash = compute_event_hash(data, GENESIS_HASH)
        event = {
            **data,
            "event_hash": event_hash,
            "prev_event_hash": GENESIS_HASH,
            "chain_sequence": 0,
        }
        assert verify_event(event, None)

    def test_valid_chained_event(self) -> None:
        prev = "a" * 64
        data = {"action": "update"}
        event_hash = compute_event_hash(data, prev)
        event = {
            **data,
            "event_hash": event_hash,
            "prev_event_hash": prev,
            "chain_sequence": 1,
        }
        assert verify_event(event, prev)

    def test_missing_hash(self) -> None:
        event: dict[str, object] = {"action": "create"}
        assert not verify_event(event, None)

    def test_tampered_data(self) -> None:
        data = {"action": "create"}
        event_hash = compute_event_hash(data, GENESIS_HASH)
        event = {
            "action": "delete",  # tampered
            "event_hash": event_hash,
            "prev_event_hash": GENESIS_HASH,
            "chain_sequence": 0,
        }
        assert not verify_event(event, None)

    def test_tampered_hash(self) -> None:
        data = {"action": "create"}
        event = {
            **data,
            "event_hash": "f" * 64,  # wrong hash
            "prev_event_hash": GENESIS_HASH,
            "chain_sequence": 0,
        }
        assert not verify_event(event, None)


class TestVerifyHashChain:
    """Tests for full chain verification."""

    def test_empty_chain(self) -> None:
        result = verify_hash_chain([])
        assert result.is_valid
        assert result.verified_count == 0
        assert result.first_break_at is None
        assert result.errors == []

    def test_single_event_chain(self) -> None:
        chain = _build_chain([{"action": "create"}])
        result = verify_hash_chain(chain)
        assert result.is_valid
        assert result.verified_count == 1

    def test_multi_event_chain(self) -> None:
        events = [{"action": f"event_{i}"} for i in range(10)]
        chain = _build_chain(events)
        result = verify_hash_chain(chain)
        assert result.is_valid
        assert result.verified_count == 10
        assert result.errors == []

    def test_tampered_event_data(self) -> None:
        chain = _build_chain(
            [
                {"action": "create"},
                {"action": "update"},
                {"action": "publish"},
            ]
        )
        # Tamper with middle event's data
        chain[1]["action"] = "tampered"
        result = verify_hash_chain(chain)
        assert not result.is_valid
        assert result.first_break_at == 1
        assert result.verified_count == 1
        assert len(result.errors) == 1
        assert "hash mismatch" in result.errors[0]

    def test_tampered_hash(self) -> None:
        chain = _build_chain(
            [
                {"action": "create"},
                {"action": "update"},
            ]
        )
        chain[0]["event_hash"] = "f" * 64
        result = verify_hash_chain(chain)
        assert not result.is_valid
        assert result.first_break_at == 0

    def test_broken_prev_hash_linkage(self) -> None:
        chain = _build_chain(
            [
                {"action": "create"},
                {"action": "update"},
                {"action": "publish"},
            ]
        )
        # Break the linkage by changing prev_event_hash
        chain[2]["prev_event_hash"] = "b" * 64
        result = verify_hash_chain(chain)
        assert not result.is_valid
        assert result.first_break_at == 2
        assert "prev_event_hash mismatch" in result.errors[0]

    def test_missing_event_hash(self) -> None:
        chain = _build_chain([{"action": "create"}])
        del chain[0]["event_hash"]
        result = verify_hash_chain(chain)
        assert not result.is_valid
        assert result.first_break_at == 0
        assert "missing event_hash" in result.errors[0]

    def test_stops_at_first_break(self) -> None:
        """Verification stops at the first integrity violation."""
        chain = _build_chain([{"action": f"event_{i}"} for i in range(5)])
        # Tamper with event 2
        chain[2]["action"] = "tampered"
        result = verify_hash_chain(chain)
        assert not result.is_valid
        assert result.first_break_at == 2
        assert result.verified_count == 2  # Only 0 and 1 verified
        assert len(result.errors) == 1


class TestChainVerificationResult:
    """Tests for the result dataclass defaults."""

    def test_defaults(self) -> None:
        result = ChainVerificationResult()
        assert result.is_valid is True
        assert result.verified_count == 0
        assert result.first_break_at is None
        assert result.errors == []
