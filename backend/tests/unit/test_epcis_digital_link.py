"""Unit tests for GS1 Digital Link utilities."""

from __future__ import annotations

import pytest

from app.modules.epcis.digital_link import (
    build_digital_link,
    is_digital_link,
    parse_digital_link,
)


class TestBuildDigitalLink:
    def test_basic_gtin_serial(self) -> None:
        uri = build_digital_link("09521568251228", serial="S100")
        assert uri == "https://id.gs1.org/01/09521568251228/21/S100"

    def test_gtin_only(self) -> None:
        uri = build_digital_link("09521568251228")
        assert uri == "https://id.gs1.org/01/09521568251228"
        assert "/21/" not in uri

    def test_with_batch(self) -> None:
        uri = build_digital_link("09521568251228", serial="S100", batch="LOT-A")
        assert uri == "https://id.gs1.org/01/09521568251228/21/S100/10/LOT-A"

    def test_custom_resolver(self) -> None:
        uri = build_digital_link("09521568251228", serial="S1", resolver="https://example.com")
        assert uri.startswith("https://example.com/01/")

    def test_resolver_trailing_slash_stripped(self) -> None:
        uri = build_digital_link("1234", resolver="https://example.com/")
        assert "example.com/01/" in uri
        assert "example.com//01/" not in uri

    def test_empty_gtin_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one digit"):
            build_digital_link("")

    def test_non_digit_gtin_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one digit"):
            build_digital_link("abc")


class TestParseDigitalLink:
    def test_basic(self) -> None:
        result = parse_digital_link("https://id.gs1.org/01/09521568251228/21/S100")
        assert result["gtin"] == "09521568251228"
        assert result["serial"] == "S100"
        assert result["resolver"] == "https://id.gs1.org"

    def test_gtin_only(self) -> None:
        result = parse_digital_link("https://id.gs1.org/01/09521568251228")
        assert result["gtin"] == "09521568251228"
        assert "serial" not in result

    def test_with_batch(self) -> None:
        result = parse_digital_link("https://id.gs1.org/01/09521568251228/21/S100/10/LOT-A")
        assert result["gtin"] == "09521568251228"
        assert result["serial"] == "S100"
        assert result["batch"] == "LOT-A"

    def test_invalid_uri_raises(self) -> None:
        with pytest.raises(ValueError, match="Not a valid GS1 Digital Link"):
            parse_digital_link("https://example.com/not/a/digital/link")

    def test_roundtrip(self) -> None:
        original = build_digital_link("09521568251228", serial="ABC-123", batch="LOT-5")
        parsed = parse_digital_link(original)
        assert parsed["gtin"] == "09521568251228"
        assert parsed["serial"] == "ABC-123"
        assert parsed["batch"] == "LOT-5"


class TestIsDigitalLink:
    def test_valid_full(self) -> None:
        assert is_digital_link("https://id.gs1.org/01/09521568251228/21/S100") is True

    def test_valid_gtin_only(self) -> None:
        assert is_digital_link("https://id.gs1.org/01/09521568251228") is True

    def test_invalid_no_01(self) -> None:
        assert is_digital_link("https://id.gs1.org/09521568251228") is False

    def test_invalid_random_url(self) -> None:
        assert is_digital_link("https://example.com/products/123") is False

    def test_invalid_empty(self) -> None:
        assert is_digital_link("") is False
