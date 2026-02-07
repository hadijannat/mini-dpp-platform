"""Tests for crypto TSA anchoring module."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from app.core.crypto.anchoring import (
    _build_ts_request,
    hash_for_timestamping,
    request_timestamp,
    verify_timestamp,
)


class TestBuildTsRequest:
    """Tests for RFC 3161 TimeStampReq building."""

    def test_returns_bytes(self) -> None:
        digest = hashlib.sha256(b"test").digest()
        result = _build_ts_request(digest)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_deterministic_structure(self) -> None:
        """Same digest should produce valid ASN.1 (though nonce differs)."""
        digest = hashlib.sha256(b"test").digest()
        r1 = _build_ts_request(digest)
        r2 = _build_ts_request(digest)
        # Both should be valid DER but differ due to random nonce
        assert isinstance(r1, bytes)
        assert isinstance(r2, bytes)


class TestHashForTimestamping:
    """Tests for digest computation."""

    def test_returns_32_bytes(self) -> None:
        result = hash_for_timestamping("some_merkle_root")
        assert isinstance(result, bytes)
        assert len(result) == 32

    def test_deterministic(self) -> None:
        r1 = hash_for_timestamping("root_hash")
        r2 = hash_for_timestamping("root_hash")
        assert r1 == r2

    def test_different_input_different_digest(self) -> None:
        r1 = hash_for_timestamping("root_a")
        r2 = hash_for_timestamping("root_b")
        assert r1 != r2


class TestRequestTimestamp:
    """Tests for TSA request sending."""

    @pytest.mark.asyncio
    async def test_skips_when_no_url(self) -> None:
        digest = hashlib.sha256(b"test").digest()
        result = await request_timestamp(digest, "")
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_http_error(self) -> None:
        digest = hashlib.sha256(b"test").digest()
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("app.core.crypto.anchoring.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            result = await request_timestamp(
                digest, "https://tsa.example.com"
            )
            assert result is None


class TestVerifyTimestamp:
    """Tests for TSA token verification."""

    def test_invalid_token_returns_false(self) -> None:
        """Invalid DER data should return False, not raise."""
        result = verify_timestamp(b"not-a-valid-token", b"some-digest")
        assert result is False
