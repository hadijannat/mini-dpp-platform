"""Tests for RFC 8785 canonicalization helpers."""

from __future__ import annotations

from app.core.crypto.canonicalization import (
    CANONICALIZATION_LEGACY_JSON_V1,
    CANONICALIZATION_RFC8785,
    canonicalize_jcs_bytes,
    sha256_hex_for_canonicalization,
    sha256_hex_jcs,
)


def test_sha256_hex_jcs_is_order_invariant() -> None:
    left = {"b": 2, "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": 2}
    assert sha256_hex_jcs(left) == sha256_hex_jcs(right)


def test_sha256_hex_for_canonicalization_supports_modes() -> None:
    payload = {"value": "ä"}
    legacy = sha256_hex_for_canonicalization(
        payload,
        canonicalization=CANONICALIZATION_LEGACY_JSON_V1,
    )
    rfc = sha256_hex_for_canonicalization(
        payload,
        canonicalization=CANONICALIZATION_RFC8785,
    )
    assert legacy != ""
    assert rfc != ""


def test_canonicalize_jcs_bytes_is_stable() -> None:
    payload = {"z": 1, "a": 2}
    assert canonicalize_jcs_bytes(payload) == canonicalize_jcs_bytes({"a": 2, "z": 1})
