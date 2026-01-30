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
