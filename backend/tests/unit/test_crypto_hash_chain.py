"""Tests for crypto hash chain module."""

from __future__ import annotations

import json

from app.core.crypto.hash_chain import (
    GENESIS_HASH,
    canonical_json,
    compute_event_hash,
)


class TestCanonicalJson:
    """Tests for deterministic JSON serialization."""

    def test_sorted_keys(self) -> None:
        data = {"z": 1, "a": 2, "m": 3}
        result = json.loads(canonical_json(data))
        assert list(result.keys()) == ["a", "m", "z"]

    def test_no_whitespace(self) -> None:
        data = {"key": "value", "num": 42}
        result = canonical_json(data)
        assert b" " not in result
        assert b"\n" not in result

    def test_nested_sorted(self) -> None:
        data = {"outer": {"z": 1, "a": 2}}
        result = canonical_json(data)
        parsed = json.loads(result)
        assert list(parsed["outer"].keys()) == ["a", "z"]

    def test_returns_bytes(self) -> None:
        result = canonical_json({"key": "value"})
        assert isinstance(result, bytes)

    def test_deterministic(self) -> None:
        """Same data always produces same bytes regardless of insertion order."""
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert canonical_json(d1) == canonical_json(d2)

    def test_empty_dict(self) -> None:
        result = canonical_json({})
        assert result == b"{}"

    def test_non_string_values_via_default_str(self) -> None:
        """Non-serializable values are converted via str()."""
        from uuid import UUID

        data = {"id": UUID("12345678-1234-5678-1234-567812345678")}
        result = canonical_json(data)
        assert b"12345678-1234-5678-1234-567812345678" in result


class TestComputeEventHash:
    """Tests for SHA-256 event hash computation."""

    def test_basic_hash(self) -> None:
        result = compute_event_hash({"action": "create"}, GENESIS_HASH)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest

    def test_deterministic(self) -> None:
        data = {"action": "create", "resource": "dpp"}
        h1 = compute_event_hash(data, GENESIS_HASH)
        h2 = compute_event_hash(data, GENESIS_HASH)
        assert h1 == h2

    def test_different_data_different_hash(self) -> None:
        h1 = compute_event_hash({"action": "create"}, GENESIS_HASH)
        h2 = compute_event_hash({"action": "delete"}, GENESIS_HASH)
        assert h1 != h2

    def test_different_prev_hash_different_result(self) -> None:
        data = {"action": "create"}
        h1 = compute_event_hash(data, GENESIS_HASH)
        h2 = compute_event_hash(data, "a" * 64)
        assert h1 != h2

    def test_chain_integrity(self) -> None:
        """Events form a chain where each hash depends on the previous."""
        e1 = compute_event_hash({"seq": 1}, GENESIS_HASH)
        e2 = compute_event_hash({"seq": 2}, e1)
        e3 = compute_event_hash({"seq": 3}, e2)

        # Changing e1 should invalidate the chain
        e1_alt = compute_event_hash({"seq": 1, "tampered": True}, GENESIS_HASH)
        e2_from_alt = compute_event_hash({"seq": 2}, e1_alt)
        assert e2_from_alt != e2
        assert e1_alt != e1

        # But the original chain is consistent
        assert compute_event_hash({"seq": 2}, e1) == e2
        assert compute_event_hash({"seq": 3}, e2) == e3


class TestGenesisHash:
    """Tests for the genesis hash constant."""

    def test_genesis_hash_is_64_zeros(self) -> None:
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64
