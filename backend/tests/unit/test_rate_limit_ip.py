"""
Unit tests for rate limiter client IP extraction with trusted proxy validation.

Verifies that X-Forwarded-For / X-Real-IP headers are only honoured
when the direct connection comes from a configured trusted proxy CIDR,
preventing IP spoofing from untrusted sources.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.core.rate_limit import _get_client_ip, _is_trusted_proxy


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    """Clear the settings LRU cache between tests."""
    get_settings.cache_clear()


def _make_request(
    connection_ip: str,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
) -> MagicMock:
    """Build a mock Starlette Request with configurable client IP and headers."""
    request = MagicMock()
    request.client.host = connection_ip

    headers: dict[str, str] = {}
    if forwarded_for is not None:
        headers["x-forwarded-for"] = forwarded_for
    if real_ip is not None:
        headers["x-real-ip"] = real_ip
    request.headers = headers

    return request


# --------------------------------------------------------------------------
# _is_trusted_proxy
# --------------------------------------------------------------------------


def test_docker_bridge_is_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    """172.18.x.x (Docker bridge) should be trusted by default CIDRs."""
    monkeypatch.setenv("TRUSTED_PROXY_CIDRS", '["172.16.0.0/12","10.0.0.0/8","127.0.0.0/8"]')
    get_settings.cache_clear()
    assert _is_trusted_proxy("172.18.0.1") is True


def test_loopback_is_trusted() -> None:
    assert _is_trusted_proxy("127.0.0.1") is True


def test_public_ip_is_not_trusted() -> None:
    assert _is_trusted_proxy("203.0.113.50") is False


def test_invalid_ip_is_not_trusted() -> None:
    assert _is_trusted_proxy("not-an-ip") is False


# --------------------------------------------------------------------------
# _get_client_ip — from trusted proxy
# --------------------------------------------------------------------------


def test_xff_honoured_from_trusted_proxy() -> None:
    """When connection is from Docker bridge, X-Forwarded-For should be used."""
    request = _make_request(
        connection_ip="172.18.0.2",
        forwarded_for="198.51.100.10, 172.18.0.2",
    )
    assert _get_client_ip(request) == "198.51.100.10"


def test_x_real_ip_honoured_from_trusted_proxy() -> None:
    """When connection is from trusted proxy and X-Real-IP is set, use it."""
    request = _make_request(
        connection_ip="10.0.0.1",
        real_ip="198.51.100.20",
    )
    assert _get_client_ip(request) == "198.51.100.20"


def test_fallback_to_connection_ip_when_headers_empty_from_trusted_proxy() -> None:
    """If no proxy headers but connection from trusted proxy, use connection IP."""
    request = _make_request(connection_ip="172.18.0.5")
    assert _get_client_ip(request) == "172.18.0.5"


# --------------------------------------------------------------------------
# _get_client_ip — from untrusted source (spoofing prevention)
# --------------------------------------------------------------------------


def test_xff_ignored_from_untrusted_source() -> None:
    """Spoofed X-Forwarded-For from a public IP should be ignored."""
    request = _make_request(
        connection_ip="203.0.113.50",
        forwarded_for="10.0.0.1",
    )
    # Should return the connection IP, NOT the spoofed header value
    assert _get_client_ip(request) == "203.0.113.50"


def test_x_real_ip_ignored_from_untrusted_source() -> None:
    """Spoofed X-Real-IP from a public IP should be ignored."""
    request = _make_request(
        connection_ip="198.51.100.99",
        real_ip="127.0.0.1",
    )
    assert _get_client_ip(request) == "198.51.100.99"


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------


def test_no_client_returns_unknown() -> None:
    """When request.client is None, return 'unknown'."""
    request = MagicMock()
    request.client = None
    request.headers = {"x-forwarded-for": "1.2.3.4"}
    assert _get_client_ip(request) == "unknown"
