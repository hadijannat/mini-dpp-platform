"""Tests for resolver schema href scheme validation (H-2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.resolver.schemas import ResolverLinkCreate, ResolverLinkUpdate


class TestResolverLinkCreateHrefScheme:
    """Verify that ResolverLinkCreate rejects non-http(s) href schemes."""

    def test_accepts_https(self) -> None:
        link = ResolverLinkCreate(
            identifier="01/09520123456788/21/SERIAL001",
            href="https://example.com/dpp/123",
        )
        assert link.href == "https://example.com/dpp/123"

    def test_accepts_http(self) -> None:
        link = ResolverLinkCreate(
            identifier="01/09520123456788",
            href="http://example.com/dpp/123",
        )
        assert link.href == "http://example.com/dpp/123"

    @pytest.mark.parametrize(
        "href",
        [
            "javascript:alert(1)",
            "data:text/html,<h1>XSS</h1>",
            "ftp://example.com/file",
            "file:///etc/passwd",
        ],
    )
    def test_rejects_dangerous_schemes(self, href: str) -> None:
        with pytest.raises(ValidationError, match="http or https"):
            ResolverLinkCreate(
                identifier="01/09520123456788",
                href=href,
            )


class TestResolverLinkUpdateHrefScheme:
    """Verify that ResolverLinkUpdate also validates href scheme."""

    def test_accepts_https(self) -> None:
        update = ResolverLinkUpdate(href="https://example.com/new")
        assert update.href == "https://example.com/new"

    def test_accepts_none(self) -> None:
        update = ResolverLinkUpdate(href=None)
        assert update.href is None

    def test_accepts_no_href(self) -> None:
        update = ResolverLinkUpdate(active=False)
        assert update.href is None

    @pytest.mark.parametrize(
        "href",
        [
            "javascript:void(0)",
            "data:text/plain,hello",
            "ftp://files.example.com",
            "file:///tmp/secret",
        ],
    )
    def test_rejects_dangerous_schemes(self, href: str) -> None:
        with pytest.raises(ValidationError, match="http or https"):
            ResolverLinkUpdate(href=href)
