"""
Unit tests for QR endpoint authorization and validation.
"""

import pytest

from app.modules.qr.service import QRCodeService


class TestHexColorValidation:
    """Tests for hex color validation in QRCodeService."""

    def setup_method(self):
        self.service = QRCodeService()

    def test_valid_hex_color_with_hash(self):
        """Valid hex color with # prefix should convert to RGB."""
        result = self.service._hex_to_rgb("#FF0000")
        assert result == (255, 0, 0)

    def test_valid_hex_color_without_hash(self):
        """Valid hex color without # prefix should convert to RGB."""
        result = self.service._hex_to_rgb("00FF00")
        assert result == (0, 255, 0)

    def test_valid_hex_color_lowercase(self):
        """Lowercase hex should work."""
        result = self.service._hex_to_rgb("#abcdef")
        assert result == (171, 205, 239)

    def test_invalid_hex_too_short(self):
        """Hex color with less than 6 characters should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service._hex_to_rgb("#FFF")
        assert "must be 6 characters" in str(exc.value)

    def test_invalid_hex_too_long(self):
        """Hex color with more than 6 characters should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service._hex_to_rgb("#FFFFFF00")
        assert "must be 6 characters" in str(exc.value)

    def test_invalid_hex_non_hex_characters(self):
        """Hex color with invalid characters should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service._hex_to_rgb("#ZZZZZZ")
        assert "Invalid hex color" in str(exc.value)

    def test_invalid_hex_mixed_invalid(self):
        """Hex color with some invalid characters should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service._hex_to_rgb("#FF00GG")
        assert "Invalid hex color" in str(exc.value)

    def test_empty_string(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service._hex_to_rgb("")
        assert "must be 6 characters" in str(exc.value)


class TestQRCodeGeneration:
    """Tests for QR code generation with validation."""

    def setup_method(self):
        self.service = QRCodeService()

    def test_generate_qr_with_valid_colors(self):
        """QR code with valid colors should generate successfully."""
        result = self.service.generate_qr_code(
            dpp_url="https://example.com/dpp/123",
            format="png",
            size=200,
            foreground_color="#000000",
            background_color="#FFFFFF",
        )
        # Should return bytes
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_qr_with_invalid_foreground_color(self):
        """QR code with invalid foreground color should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service.generate_qr_code(
                dpp_url="https://example.com/dpp/123",
                format="png",
                size=200,
                foreground_color="#INVALID",
                background_color="#FFFFFF",
            )
        assert "Invalid hex color" in str(exc.value)

    def test_generate_qr_with_invalid_background_color(self):
        """QR code with invalid background color should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            self.service.generate_qr_code(
                dpp_url="https://example.com/dpp/123",
                format="png",
                size=200,
                foreground_color="#000000",
                background_color="not-a-color",
            )
        assert "Invalid hex color" in str(exc.value)

    def test_generate_svg_format(self):
        """SVG format should generate successfully."""
        result = self.service.generate_qr_code(
            dpp_url="https://example.com/dpp/123",
            format="svg",
            size=200,
        )
        assert isinstance(result, bytes)
        # SVG starts with XML declaration or svg tag
        content = result.decode("utf-8")
        assert "svg" in content.lower()


# ---------------------------------------------------------------------------
# GS1 Digital Link construction
# ---------------------------------------------------------------------------


class TestGS1DigitalLink:
    """Tests for QRCodeService.build_gs1_digital_link."""

    def setup_method(self):
        self.service = QRCodeService()

    def test_gs1_link_format(self):
        """Standard 14-digit GTIN + serial produces the canonical GS1 link."""
        url = self.service.build_gs1_digital_link("01234567890123", "SN001")
        assert url == "https://id.gs1.org/01/01234567890123/21/SN001"

    def test_gtin_padded_to_14_digits(self):
        """Short GTIN is zero-padded on the left to 14 digits."""
        url = self.service.build_gs1_digital_link("12345", "SN001")
        assert "/01/00000000012345/" in url

    def test_gtin_non_digits_stripped(self):
        """Non-digit characters are stripped from the GTIN."""
        url = self.service.build_gs1_digital_link("123-456-789", "SN001")
        # Only digits remain; the cleaned value is 123456789 -> padded to 14
        assert "/01/00000123456789/" in url

    def test_serial_special_chars_encoded(self):
        """Special characters in the serial number are URL-encoded."""
        url = self.service.build_gs1_digital_link("01234567890123", "SN/2024 #01")
        # "/" -> %2F, " " -> %20, "#" -> %23
        assert "SN%2F2024%20%2301" in url

    def test_custom_resolver_url(self):
        """A custom resolver_url replaces the default GS1 resolver."""
        url = self.service.build_gs1_digital_link(
            "01234567890123", "SN001", resolver_url="https://resolver.example.com"
        )
        assert url.startswith("https://resolver.example.com/01/")

    def test_custom_resolver_trailing_slash_stripped(self):
        """Trailing slash on the custom resolver is stripped to avoid //."""
        url = self.service.build_gs1_digital_link(
            "01234567890123", "SN001", resolver_url="https://resolver.example.com/"
        )
        assert "resolver.example.com/01/" in url
        assert "resolver.example.com//01/" not in url

    def test_empty_gtin_raises(self):
        """Empty GTIN raises ValueError."""
        with pytest.raises(ValueError, match="GTIN is required"):
            self.service.build_gs1_digital_link("", "SN001")

    def test_empty_serial_raises(self):
        """Empty serial raises ValueError."""
        with pytest.raises(ValueError, match="Serial number is required"):
            self.service.build_gs1_digital_link("01234567890123", "")


# ---------------------------------------------------------------------------
# Asset-ID GTIN / serial extraction
# ---------------------------------------------------------------------------


class TestAssetIdExtraction:
    """Tests for QRCodeService.extract_gtin_from_asset_ids."""

    def setup_method(self):
        self.service = QRCodeService()

    def test_explicit_gtin_field(self):
        """When asset_ids contains 'gtin', it is returned directly."""
        gtin, _ = self.service.extract_gtin_from_asset_ids(
            {"gtin": "01234567890123", "serialNumber": "SN001"}
        )
        assert gtin == "01234567890123"

    def test_numeric_global_asset_id_fallback(self):
        """Numeric globalAssetId is used as GTIN when no explicit gtin key."""
        gtin, _ = self.service.extract_gtin_from_asset_ids(
            {"globalAssetId": "09876543210987", "serialNumber": "SN002"}
        )
        assert gtin == "09876543210987"

    def test_non_numeric_global_asset_id_ignored(self):
        """Non-numeric globalAssetId (e.g., URN) does not become the GTIN."""
        gtin, _ = self.service.extract_gtin_from_asset_ids(
            {
                "globalAssetId": "urn:uuid:abc-123",
                "manufacturerPartId": "PART-42",
                "serialNumber": "SN003",
            }
        )
        # Should fall through to pseudo-GTIN; definitely not the URN
        assert gtin != "urn:uuid:abc-123"

    def test_pseudo_gtin_deterministic(self):
        """Same manufacturerPartId always produces the same pseudo-GTIN."""
        ids = {"manufacturerPartId": "PART-42", "serialNumber": "SN004"}
        gtin_a, _ = self.service.extract_gtin_from_asset_ids(ids)
        gtin_b, _ = self.service.extract_gtin_from_asset_ids(ids)
        assert gtin_a == gtin_b

    def test_pseudo_gtin_numeric_only(self):
        """Pseudo-GTIN consists of digits only."""
        gtin, _ = self.service.extract_gtin_from_asset_ids(
            {"manufacturerPartId": "PART-XYZ", "serialNumber": "SN005"}
        )
        assert gtin.isdigit()

    def test_serial_from_asset_ids(self):
        """serialNumber is extracted from asset_ids."""
        _, serial = self.service.extract_gtin_from_asset_ids(
            {"gtin": "01234567890123", "serialNumber": "SN-EXPECTED"}
        )
        assert serial == "SN-EXPECTED"

    def test_missing_serial_returns_empty(self):
        """When serialNumber key is absent, serial is empty string."""
        _, serial = self.service.extract_gtin_from_asset_ids({"gtin": "01234567890123"})
        assert serial == ""
