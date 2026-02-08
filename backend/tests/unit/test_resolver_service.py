"""Tests for the GS1 Digital Link resolver service."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.modules.resolver.schemas import LinkType, ResolverLinkCreate, ResolverLinkUpdate
from app.modules.resolver.service import ResolverService


def _make_link(
    *,
    identifier: str = "01/09520123456788/21/SER001",
    link_type: str = LinkType.HAS_DPP.value,
    href: str = "https://example.com/dpp/123",
    media_type: str = "application/json",
    title: str = "Test DPP",
    hreflang: str = "en",
    priority: int = 100,
    active: bool = True,
) -> MagicMock:
    """Create a mock ResolverLink."""
    link = MagicMock()
    link.id = uuid4()
    link.tenant_id = uuid4()
    link.identifier = identifier
    link.link_type = link_type
    link.href = href
    link.media_type = media_type
    link.title = title
    link.hreflang = hreflang
    link.priority = priority
    link.dpp_id = uuid4()
    link.active = active
    link.created_by_subject = "test-user"
    link.created_at = datetime.now()
    link.updated_at = datetime.now()
    return link


class TestBuildLinkset:
    """Tests for the static build_linkset method."""

    def test_empty_links(self) -> None:
        result = ResolverService.build_linkset([], "https://example.com/01/123")
        assert result == {"linkset": [{"anchor": "https://example.com/01/123"}]}

    def test_single_link(self) -> None:
        link = _make_link()
        result = ResolverService.build_linkset([link], "https://resolver.example.com/01/123")
        assert len(result["linkset"]) == 1
        entry = result["linkset"][0]
        assert entry["anchor"] == "https://resolver.example.com/01/123"
        assert LinkType.HAS_DPP.value in entry
        link_entries = entry[LinkType.HAS_DPP.value]
        assert len(link_entries) == 1
        assert link_entries[0]["href"] == "https://example.com/dpp/123"

    def test_multiple_link_types(self) -> None:
        link1 = _make_link(link_type=LinkType.HAS_DPP.value)
        link2 = _make_link(
            link_type=LinkType.CERTIFICATION_INFO.value, href="https://cert.example.com"
        )
        result = ResolverService.build_linkset(
            [link1, link2], "https://resolver.example.com/01/123"
        )
        entry = result["linkset"][0]
        assert LinkType.HAS_DPP.value in entry
        assert LinkType.CERTIFICATION_INFO.value in entry

    def test_grouped_same_type(self) -> None:
        link1 = _make_link(href="https://a.com")
        link2 = _make_link(href="https://b.com")
        result = ResolverService.build_linkset(
            [link1, link2], "https://resolver.example.com/01/123"
        )
        entry = result["linkset"][0]
        dpp_links = entry[LinkType.HAS_DPP.value]
        assert len(dpp_links) == 2
        hrefs = {e["href"] for e in dpp_links}
        assert hrefs == {"https://a.com", "https://b.com"}


class TestResolverLinkCreate:
    """Tests for ResolverLinkCreate schema validation."""

    def test_valid_create(self) -> None:
        data = ResolverLinkCreate(
            identifier="01/09520123456788/21/SER001",
            link_type=LinkType.HAS_DPP,
            href="https://example.com/dpp/123",
        )
        assert data.identifier == "01/09520123456788/21/SER001"
        assert data.link_type == LinkType.HAS_DPP
        assert data.media_type == "application/json"
        assert data.priority == 0

    def test_defaults(self) -> None:
        data = ResolverLinkCreate(
            identifier="01/123",
            href="https://example.com",
        )
        assert data.link_type == LinkType.HAS_DPP
        assert data.hreflang == "en"
        assert data.title == ""

    def test_priority_bounds(self) -> None:
        data = ResolverLinkCreate(
            identifier="01/123",
            href="https://example.com",
            priority=1000,
        )
        assert data.priority == 1000

        with pytest.raises(ValueError):
            ResolverLinkCreate(
                identifier="01/123",
                href="https://example.com",
                priority=1001,
            )


class TestResolverLinkUpdate:
    """Tests for ResolverLinkUpdate partial update schema."""

    def test_partial_update(self) -> None:
        update = ResolverLinkUpdate(href="https://new.example.com")
        dumped = update.model_dump(exclude_unset=True)
        assert dumped == {"href": "https://new.example.com"}

    def test_all_none_by_default(self) -> None:
        update = ResolverLinkUpdate()
        dumped = update.model_dump(exclude_unset=True)
        assert dumped == {}


class TestLinkType:
    """Tests for the LinkType enum."""

    def test_values(self) -> None:
        assert LinkType.HAS_DPP.value == "gs1:hasDigitalProductPassport"
        assert LinkType.PIP.value == "gs1:pip"
        assert LinkType.CERTIFICATION_INFO.value == "gs1:certificationInfo"
