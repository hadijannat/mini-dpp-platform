"""Comprehensive tests for GS1 check digit computation and GTIN validation.

Covers GTIN-8, GTIN-12, GTIN-13, GTIN-14 formats, edge cases,
and the GS1 Digital Link builder.
"""

import pytest

from app.modules.qr.service import QRCodeService


class TestComputeGTINCheckDigit:
    """Tests for _compute_gtin_check_digit per GS1 General Specifications Section 7.9."""

    def test_gtin8_known_value(self) -> None:
        # GTIN-8: 96385074 → payload 9638507, check digit 4
        assert QRCodeService._compute_gtin_check_digit("9638507") == "4"

    def test_gtin12_known_value(self) -> None:
        # UPC-A: 036000291452 → payload 03600029145, check digit 2
        assert QRCodeService._compute_gtin_check_digit("03600029145") == "2"

    def test_gtin13_known_value(self) -> None:
        # EAN-13: 4006381333931 → payload 400638133393, check digit 1
        assert QRCodeService._compute_gtin_check_digit("400638133393") == "1"

    def test_gtin14_known_value(self) -> None:
        # GTIN-14: 10614141000415 → payload 1061414100041, check digit 5
        assert QRCodeService._compute_gtin_check_digit("1061414100041") == "5"

    def test_another_gtin13(self) -> None:
        # EAN-13: 5901234123457 → payload 590123412345, check digit 7
        assert QRCodeService._compute_gtin_check_digit("590123412345") == "7"

    def test_all_zeros_gtin8(self) -> None:
        # 0000000 → all zeros, sum=0, check digit=0
        assert QRCodeService._compute_gtin_check_digit("0000000") == "0"

    def test_all_zeros_gtin13(self) -> None:
        assert QRCodeService._compute_gtin_check_digit("000000000000") == "0"

    def test_all_zeros_gtin14(self) -> None:
        assert QRCodeService._compute_gtin_check_digit("0000000000000") == "0"

    def test_all_nines_gtin8(self) -> None:
        # 9999999: weights (right to left): 3,1,3,1,3,1,3
        # sum = 9*(3+1+3+1+3+1+3) = 9*15 = 135
        # check = (10 - (135 % 10)) % 10 = (10-5) % 10 = 5
        assert QRCodeService._compute_gtin_check_digit("9999999") == "5"

    def test_all_nines_gtin13(self) -> None:
        # 999999999999: 12 digits, weights alternate 3,1,...
        # sum = 9*(3+1)*6 = 9*24 = 216
        # check = (10 - (216 % 10)) % 10 = (10-6) % 10 = 4
        assert QRCodeService._compute_gtin_check_digit("999999999999") == "4"

    def test_all_nines_gtin14(self) -> None:
        # 9999999999999: 13 digits, weights 3,1,3,1,...
        # sum = 9*(3+1+3+1+3+1+3+1+3+1+3+1+3) = 9*27 = 243
        # check = (10 - (243 % 10)) % 10 = (10-3) % 10 = 7
        assert QRCodeService._compute_gtin_check_digit("9999999999999") == "7"

    def test_single_digit(self) -> None:
        # Edge case: single digit payload
        # digit 5, weight 3: sum=15, check=(10-5)%10=5
        assert QRCodeService._compute_gtin_check_digit("5") == "5"


class TestValidateGTIN:
    """Tests for validate_gtin static method."""

    def test_valid_gtin8(self) -> None:
        assert QRCodeService.validate_gtin("96385074") is True

    def test_valid_gtin12(self) -> None:
        assert QRCodeService.validate_gtin("036000291452") is True

    def test_valid_gtin13(self) -> None:
        assert QRCodeService.validate_gtin("4006381333931") is True

    def test_valid_gtin14(self) -> None:
        assert QRCodeService.validate_gtin("10614141000415") is True

    def test_invalid_gtin8_wrong_check(self) -> None:
        assert QRCodeService.validate_gtin("96385070") is False

    def test_invalid_gtin13_wrong_check(self) -> None:
        assert QRCodeService.validate_gtin("4006381333930") is False

    def test_invalid_length_9(self) -> None:
        assert QRCodeService.validate_gtin("123456789") is False

    def test_invalid_length_10(self) -> None:
        assert QRCodeService.validate_gtin("1234567890") is False

    def test_invalid_length_11(self) -> None:
        assert QRCodeService.validate_gtin("12345678901") is False

    def test_invalid_length_15(self) -> None:
        assert QRCodeService.validate_gtin("123456789012345") is False

    def test_empty_string(self) -> None:
        assert QRCodeService.validate_gtin("") is False

    def test_non_digit_characters_stripped(self) -> None:
        # validate_gtin strips non-digits, then checks length
        # "9638-5074" → "96385074" (8 digits, valid GTIN-8)
        assert QRCodeService.validate_gtin("9638-5074") is True

    def test_all_zeros_gtin8_valid(self) -> None:
        assert QRCodeService.validate_gtin("00000000") is True

    def test_all_zeros_gtin14_valid(self) -> None:
        assert QRCodeService.validate_gtin("00000000000000") is True


class TestBuildGS1DigitalLink:
    """Tests for build_gs1_digital_link method."""

    def test_valid_gtin_link(self) -> None:
        service = QRCodeService()
        # Use a known-valid GTIN-14
        gtin = "10614141000415"
        link = service.build_gs1_digital_link(gtin, "SN-001")
        assert link == "https://id.gs1.org/01/10614141000415/21/SN-001"

    def test_gtin_padded_to_14(self) -> None:
        service = QRCodeService()
        # GTIN-8 "96385074" zero-padded to "00000096385074".
        # Leading zeros don't affect the check digit (0 * weight = 0),
        # so the check digit remains valid after padding.
        link = service.build_gs1_digital_link("96385074", "SN-001")
        assert "/01/00000096385074/21/SN-001" in link

    def test_gtin14_already_valid(self) -> None:
        service = QRCodeService()
        # A valid 14-digit GTIN should not be padded
        link = service.build_gs1_digital_link("10614141000415", "SN-002")
        assert "/01/10614141000415/" in link

    def test_invalid_check_digit_raises(self) -> None:
        service = QRCodeService()
        # GTIN with wrong check digit should raise ValueError
        with pytest.raises(ValueError, match="invalid check digit"):
            service.build_gs1_digital_link("10614141000410", "SN-001")

    def test_empty_gtin_raises(self) -> None:
        service = QRCodeService()
        with pytest.raises(ValueError, match="GTIN is required"):
            service.build_gs1_digital_link("", "SN-001")

    def test_empty_serial_raises(self) -> None:
        service = QRCodeService()
        with pytest.raises(ValueError, match="Serial number is required"):
            service.build_gs1_digital_link("10614141000415", "")

    def test_custom_resolver_url(self) -> None:
        service = QRCodeService()
        link = service.build_gs1_digital_link(
            "10614141000415",
            "SN-001",
            resolver_url="https://custom.resolver.example.com/",
        )
        assert link.startswith("https://custom.resolver.example.com/01/")

    def test_serial_url_encoded(self) -> None:
        service = QRCodeService()
        link = service.build_gs1_digital_link("10614141000415", "SN 001/A")
        assert "SN%20001%2FA" in link


class TestExtractGTINFromAssetIds:
    """Tests for extract_gtin_from_asset_ids method."""

    def test_explicit_gtin(self) -> None:
        service = QRCodeService()
        gtin, serial, is_pseudo = service.extract_gtin_from_asset_ids(
            {"gtin": "10614141000415", "serialNumber": "SN-001"}
        )
        assert gtin == "10614141000415"
        assert serial == "SN-001"
        assert is_pseudo is False

    def test_pseudo_gtin_generated(self) -> None:
        service = QRCodeService()
        gtin, serial, is_pseudo = service.extract_gtin_from_asset_ids(
            {"manufacturerPartId": "MP-123", "serialNumber": "SN-001"}
        )
        assert len(gtin) == 14
        assert is_pseudo is True
        # Pseudo GTIN should have valid check digit
        assert QRCodeService.validate_gtin(gtin) is True

    def test_global_asset_id_as_gtin(self) -> None:
        service = QRCodeService()
        gtin, serial, is_pseudo = service.extract_gtin_from_asset_ids(
            {"globalAssetId": "10614141000415", "serialNumber": "SN-001"}
        )
        assert gtin == "10614141000415"
        assert is_pseudo is False

    def test_global_asset_id_non_numeric_ignored(self) -> None:
        service = QRCodeService()
        gtin, serial, is_pseudo = service.extract_gtin_from_asset_ids(
            {
                "globalAssetId": "urn:asset:1",
                "manufacturerPartId": "MP-123",
                "serialNumber": "SN-001",
            }
        )
        assert is_pseudo is True

    def test_pseudo_gtin_deterministic(self) -> None:
        service = QRCodeService()
        gtin1, _, _ = service.extract_gtin_from_asset_ids(
            {"manufacturerPartId": "MP-123", "serialNumber": "SN-001"}
        )
        gtin2, _, _ = service.extract_gtin_from_asset_ids(
            {"manufacturerPartId": "MP-123", "serialNumber": "SN-001"}
        )
        assert gtin1 == gtin2
