"""Tests for IEC 61406 Identification Link functionality."""

from __future__ import annotations

from app.modules.qr.service import QRCodeService
from app.modules.resolver.schemas import LinkType


class TestIEC61406LinkType:
    """Tests for the IEC 61406 link type enum value."""

    def test_link_type_exists(self) -> None:
        assert hasattr(LinkType, "IEC61406_ID")

    def test_link_type_value(self) -> None:
        assert LinkType.IEC61406_ID.value == "iec61406:identificationLink"

    def test_link_type_is_string_enum(self) -> None:
        assert isinstance(LinkType.IEC61406_ID, str)
        assert isinstance(LinkType.IEC61406_ID, LinkType)


class TestBuildIEC61406Link:
    """Tests for QRCodeService.build_iec61406_link()."""

    def test_basic_link_generation(self) -> None:
        svc = QRCodeService()
        link = svc.build_iec61406_link(
            {"manufacturerPartId": "PART-001", "serialNumber": "SN-123"},
            "https://example.com/dpp/abc",
        )
        assert link.startswith("https://example.com/dpp/abc")
        assert "mid=PART-001" in link
        assert "sn=SN-123" in link

    def test_url_encoding_special_chars(self) -> None:
        svc = QRCodeService()
        link = svc.build_iec61406_link(
            {
                "manufacturerPartId": "PART 001#2",
                "serialNumber": "SN&123",
            },
            "https://example.com",
        )
        # Spaces and special characters should be percent-encoded
        assert "mid=PART%20001%232" in link
        assert "sn=SN%26123" in link

    def test_empty_asset_ids(self) -> None:
        svc = QRCodeService()
        link = svc.build_iec61406_link({}, "https://example.com")
        assert "mid=" in link
        assert "sn=" in link

    def test_trailing_slash_stripped(self) -> None:
        svc = QRCodeService()
        link = svc.build_iec61406_link(
            {"manufacturerPartId": "P1", "serialNumber": "S1"},
            "https://example.com/dpp/",
        )
        assert "//?" not in link
        assert link.startswith("https://example.com/dpp?")
