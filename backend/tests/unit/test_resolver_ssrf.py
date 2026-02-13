"""SSRF negative tests for resolver link schemas (TEST-002).

Mirrors the webhook SSRF test suite to ensure resolver links reject
private/internal URLs on both create and update paths.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.resolver.schemas import ResolverLinkCreate, ResolverLinkUpdate

_VALID_IDENTIFIER = "01/09520123456788/21/SERIAL001"


# ── ResolverLinkCreate SSRF Tests ──────────────────────────────────


class TestResolverLinkCreateSSRF:
    """Verify that ResolverLinkCreate rejects private/internal URLs."""

    @pytest.mark.parametrize(
        "href",
        [
            "http://localhost:8000/internal",
            "http://127.0.0.1:8000/api",
            "http://127.0.0.99/",
            "http://10.0.0.1/internal",
            "http://10.255.255.255/",
            "http://172.16.0.1/internal",
            "http://172.31.255.255/internal",
            "http://192.168.1.1/internal",
            "http://192.168.0.100/",
            "http://169.254.169.254/latest/meta-data/",
            "http://0.0.0.0/",
        ],
        ids=[
            "localhost",
            "loopback-127.0.0.1",
            "loopback-127.0.0.99",
            "private-10.0.0.1",
            "private-10.255.255.255",
            "private-172.16.0.1",
            "private-172.31.255.255",
            "private-192.168.1.1",
            "private-192.168.0.100",
            "metadata-169.254",
            "zero-address",
        ],
    )
    def test_rejects_private_ipv4_urls(self, href: str) -> None:
        with pytest.raises(ValidationError, match="private or internal"):
            ResolverLinkCreate(identifier=_VALID_IDENTIFIER, href=href)

    @pytest.mark.parametrize(
        "href",
        [
            "http://[::1]/internal",
            "http://[fe80::1]/internal",
        ],
        ids=["ipv6-loopback", "ipv6-link-local"],
    )
    def test_rejects_private_ipv6_urls(self, href: str) -> None:
        with pytest.raises(ValidationError, match="private or internal"):
            ResolverLinkCreate(identifier=_VALID_IDENTIFIER, href=href)

    def test_accepts_public_url(self) -> None:
        link = ResolverLinkCreate(
            identifier=_VALID_IDENTIFIER,
            href="https://example.com/dpp/123",
        )
        assert link.href == "https://example.com/dpp/123"

    def test_accepts_public_ip(self) -> None:
        link = ResolverLinkCreate(
            identifier=_VALID_IDENTIFIER,
            href="https://93.184.216.34/dpp/abc",
        )
        assert "93.184" in link.href

    def test_rejects_url_without_hostname(self) -> None:
        with pytest.raises(ValidationError):
            ResolverLinkCreate(identifier=_VALID_IDENTIFIER, href="https:///no-host")


# ── ResolverLinkUpdate SSRF Tests ──────────────────────────────────


class TestResolverLinkUpdateSSRF:
    """Verify that ResolverLinkUpdate also rejects private/internal URLs."""

    @pytest.mark.parametrize(
        "href",
        [
            "http://localhost:8000/internal",
            "http://127.0.0.1:8000/api",
            "http://10.0.0.1/internal",
            "http://172.16.0.1/internal",
            "http://192.168.1.1/internal",
            "http://169.254.169.254/latest/meta-data/",
        ],
    )
    def test_update_rejects_private_urls(self, href: str) -> None:
        with pytest.raises(ValidationError, match="private or internal"):
            ResolverLinkUpdate(href=href)

    def test_update_accepts_public_url(self) -> None:
        update = ResolverLinkUpdate(href="https://hooks.example.com/dpp")
        assert "example.com" in (update.href or "")

    def test_update_accepts_none_url(self) -> None:
        update = ResolverLinkUpdate(href=None)
        assert update.href is None

    def test_update_accepts_no_href(self) -> None:
        update = ResolverLinkUpdate(active=False)
        assert update.href is None
