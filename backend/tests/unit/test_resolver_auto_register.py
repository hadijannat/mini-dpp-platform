"""Tests for auto_register_for_dpp in the GS1 Digital Link resolver service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.resolver.service import ResolverService


@pytest.fixture()
def tenant_id():
    return uuid4()


@pytest.fixture()
def created_by():
    return "test-subject"


@pytest.fixture()
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_dpp(
    *,
    gtin: str = "09520123456788",
    serial: str = "SER001",
    tenant_slug: str | None = "default",
):
    """Create a mock DPP with configurable asset_ids."""
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.tenant_slug = tenant_slug
    asset_ids: dict[str, str] = {}
    if gtin:
        asset_ids["gtin"] = gtin
    if serial:
        asset_ids["serialNumber"] = serial
    if not gtin:
        asset_ids["manufacturerPartId"] = "PART-001"
    dpp.asset_ids = asset_ids
    return dpp


class TestAutoRegisterForDPP:
    """Tests for ResolverService.auto_register_for_dpp."""

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_creates_link_for_valid_gtin_serial(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """DPP with valid GTIN+serial gets resolver links created (GS1 + IEC 61406)."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp()

        # No existing links (GS1 check + IEC 61406 check)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        # Two links added: GS1 DPP + IEC 61406
        assert mock_session.add.call_count == 2
        gs1_link = mock_session.add.call_args_list[0][0][0]
        assert gs1_link.identifier == "01/09520123456788/21/SER001"
        assert gs1_link.link_type == "gs1:hasDigitalProductPassport"
        assert gs1_link.tenant_id == tenant_id
        assert gs1_link.created_by_subject == created_by
        assert str(dpp.id) in gs1_link.href

        iec_link = mock_session.add.call_args_list[1][0][0]
        assert iec_link.link_type == "iec61406:identificationLink"
        assert iec_link.tenant_id == tenant_id

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_missing_gtin_skips_no_exception(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Missing GTIN causes a skip (no link created, no exception)."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp(gtin="")

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        mock_session.add.assert_not_called()

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_missing_serial_skips_no_exception(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Missing serial number causes a skip."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp(serial="")

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        mock_session.add.assert_not_called()

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_idempotency_does_not_create_duplicate(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Calling twice does not create a duplicate -- existing link is detected."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp()

        # Existing link found
        existing_link = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_link
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        mock_session.add.assert_not_called()

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_tenant_slug_db_fallback(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """When dpp.tenant_slug is not set, falls back to DB lookup."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp(tenant_slug=None)

        # 1: check for existing GS1 link (none)
        no_link_result = MagicMock()
        no_link_result.scalar_one_or_none.return_value = None
        # 2: tenant slug lookup
        tenant_slug_result = MagicMock()
        tenant_slug_result.scalar_one_or_none.return_value = "my-tenant"
        # 3: check for existing IEC 61406 link (none)
        no_iec_result = MagicMock()
        no_iec_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[no_link_result, tenant_slug_result, no_iec_result]
        )

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        assert mock_session.add.call_count == 2
        gs1_link = mock_session.add.call_args_list[0][0][0]
        assert "/my-tenant/" in gs1_link.href

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_tenant_slug_db_fallback_defaults_to_default(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """When dpp.tenant_slug is not set and DB lookup returns None, uses 'default'."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp(tenant_slug=None)

        # 1: no existing GS1 link; 2: no tenant found; 3: no IEC link
        no_link_result = MagicMock()
        no_link_result.scalar_one_or_none.return_value = None
        no_tenant_result = MagicMock()
        no_tenant_result.scalar_one_or_none.return_value = None
        no_iec_result = MagicMock()
        no_iec_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[no_link_result, no_tenant_result, no_iec_result]
        )

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://example.com",
        )

        assert mock_session.add.call_count == 2
        gs1_link = mock_session.add.call_args_list[0][0][0]
        assert "/default/" in gs1_link.href

    @pytest.mark.asyncio()
    @patch("app.modules.qr.service.QRCodeService")
    async def test_href_construction(
        self,
        mock_qr_cls: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Verify the constructed href follows the expected pattern."""
        mock_qr = MagicMock()
        mock_qr.extract_gtin_from_asset_ids.return_value = ("09520123456788", "SER001", False)
        mock_qr_cls.return_value = mock_qr

        dpp = _make_dpp(tenant_slug="acme")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = ResolverService(mock_session)
        await svc.auto_register_for_dpp(
            dpp=dpp,
            tenant_id=tenant_id,
            created_by=created_by,
            base_url="https://dpp.example.com/",
        )

        gs1_link = mock_session.add.call_args_list[0][0][0]
        expected_href = f"https://dpp.example.com/api/v1/public/acme/dpps/{dpp.id}"
        assert gs1_link.href == expected_href
