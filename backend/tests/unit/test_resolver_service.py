"""Tests for the GS1 Digital Link resolver service."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

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


# ==========================================================================
# CRUD service method tests
# ==========================================================================


@pytest.fixture()
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestListLinks:
    """Tests for ResolverService.list_links with active_only filtering."""

    @pytest.mark.asyncio()
    async def test_list_links_active_only_true(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """list_links with active_only=True returns only active links."""
        active_link = _make_link(active=True)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_link]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.list_links(tenant_id, active_only=True)

        assert len(result) == 1
        assert result[0].active is True

    @pytest.mark.asyncio()
    async def test_list_links_active_only_false(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """list_links with active_only=False returns active and inactive links."""
        active_link = _make_link(active=True)
        inactive_link = _make_link(active=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [active_link, inactive_link]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.list_links(tenant_id, active_only=False)

        assert len(result) == 2


class TestUpdateLink:
    """Tests for ResolverService.update_link applying partial updates."""

    @pytest.mark.asyncio()
    async def test_update_link_applies_partial_updates(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """update_link applies only the fields provided in the update."""
        existing_link = _make_link(href="https://old.example.com", title="Old Title")
        link_id = existing_link.id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_link
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        update = ResolverLinkUpdate(href="https://new.example.com")
        result = await svc.update_link(link_id, tenant_id, update)

        assert result is not None
        assert result.href == "https://new.example.com"
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_update_link_returns_none_for_missing(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """update_link returns None when the link does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        update = ResolverLinkUpdate(href="https://new.example.com")
        result = await svc.update_link(uuid4(), tenant_id, update)

        assert result is None


class TestDeleteLink:
    """Tests for ResolverService.delete_link."""

    @pytest.mark.asyncio()
    async def test_delete_link_returns_false_for_missing(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """delete_link returns False when the link does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.delete_link(uuid4(), tenant_id)

        assert result is False

    @pytest.mark.asyncio()
    async def test_delete_link_returns_true_for_existing(
        self, mock_session: AsyncMock, tenant_id: UUID
    ) -> None:
        """delete_link returns True and deletes when the link exists."""
        existing_link = _make_link()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_link
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.delete_link(existing_link.id, tenant_id)

        assert result is True
        mock_session.delete.assert_awaited_once_with(existing_link)
        mock_session.flush.assert_awaited_once()


class TestResolveWithFilter:
    """Tests for ResolverService.resolve with link_type_filter."""

    @pytest.mark.asyncio()
    async def test_resolve_with_link_type_filter(self, mock_session: AsyncMock) -> None:
        """resolve with link_type_filter returns only matching link types."""
        cert_link = _make_link(link_type=LinkType.CERTIFICATION_INFO.value)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [cert_link]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.resolve(
            "01/09520123456788/21/SER001",
            link_type_filter=LinkType.CERTIFICATION_INFO.value,
        )

        assert len(result) == 1
        assert result[0].link_type == LinkType.CERTIFICATION_INFO.value

    @pytest.mark.asyncio()
    async def test_resolve_without_filter(self, mock_session: AsyncMock) -> None:
        """resolve without link_type_filter returns all active links."""
        link1 = _make_link(link_type=LinkType.HAS_DPP.value)
        link2 = _make_link(link_type=LinkType.CERTIFICATION_INFO.value)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [link1, link2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.resolve("01/09520123456788/21/SER001")

        assert len(result) == 2

    @pytest.mark.asyncio()
    async def test_resolve_empty_results(self, mock_session: AsyncMock) -> None:
        """resolve returns empty list when no links match."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        result = await svc.resolve("01/00000000000000/21/UNKNOWN")

        assert result == []
