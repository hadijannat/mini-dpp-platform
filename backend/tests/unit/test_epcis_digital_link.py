"""Unit tests for GS1 Digital Link utilities."""

from __future__ import annotations

import pytest

from app.modules.epcis.digital_link import (
    build_digital_link,
    build_digital_link_for_dpp,
    enrich_epcis_with_digital_link,
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


class TestBuildDigitalLinkForDpp:
    def test_with_valid_gtin_manufacturer_part_id(self) -> None:
        uri = build_digital_link_for_dpp({"manufacturerPartId": "09521568251228"})
        assert uri is not None
        assert "/01/09521568251228" in uri
        assert uri.startswith("https://id.gs1.org/")

    def test_with_explicit_gtin_key(self) -> None:
        uri = build_digital_link_for_dpp({"gtin": "12345678"})
        assert uri is not None
        assert "/01/12345678" in uri

    def test_gtin_preferred_over_manufacturer_part_id(self) -> None:
        uri = build_digital_link_for_dpp(
            {
                "gtin": "11111111",
                "manufacturerPartId": "22222222",
            }
        )
        assert uri is not None
        assert "/01/11111111" in uri

    def test_returns_none_when_no_gtin(self) -> None:
        assert build_digital_link_for_dpp({"serialNumber": "SN-001"}) is None

    def test_returns_none_for_non_digit_part_id(self) -> None:
        assert build_digital_link_for_dpp({"manufacturerPartId": "PART-ABC"}) is None

    def test_returns_none_for_too_short_digits(self) -> None:
        assert build_digital_link_for_dpp({"manufacturerPartId": "1234567"}) is None

    def test_returns_none_for_too_long_digits(self) -> None:
        assert build_digital_link_for_dpp({"manufacturerPartId": "123456789012345"}) is None

    def test_custom_resolver(self) -> None:
        uri = build_digital_link_for_dpp(
            {"gtin": "09521568251228"},
            resolver="https://example.com",
        )
        assert uri is not None
        assert uri.startswith("https://example.com/")

    def test_empty_asset_ids(self) -> None:
        assert build_digital_link_for_dpp({}) is None

    def test_whitespace_trimmed(self) -> None:
        uri = build_digital_link_for_dpp({"manufacturerPartId": " 09521568251228 "})
        assert uri is not None
        assert "/01/09521568251228" in uri


class TestEnrichEpcisWithDigitalLink:
    def test_adds_digital_link_uri(self) -> None:
        payload: dict[str, object] = {"epcList": ["urn:epc:id:sgtin:0614141.107346.2017"]}
        result = enrich_epcis_with_digital_link(payload, "https://id.gs1.org/01/09521568251228")
        assert result["digitalLinkURI"] == "https://id.gs1.org/01/09521568251228"

    def test_does_not_overwrite_existing(self) -> None:
        payload: dict[str, object] = {
            "digitalLinkURI": "https://id.gs1.org/01/EXISTING",
            "epcList": [],
        }
        result = enrich_epcis_with_digital_link(payload, "https://id.gs1.org/01/NEW")
        assert result["digitalLinkURI"] == "https://id.gs1.org/01/EXISTING"

    def test_returns_same_dict(self) -> None:
        payload: dict[str, object] = {}
        result = enrich_epcis_with_digital_link(payload, "https://id.gs1.org/01/1234")
        assert result is payload
