"""Unit tests for data carrier compliance profile parsing."""

from app.modules.data_carriers.profile import (
    DataCarrierComplianceProfile,
    default_data_carrier_compliance_profile,
    parse_data_carrier_compliance_profile,
)


def test_default_profile_matches_expected_baseline() -> None:
    profile = default_data_carrier_compliance_profile()
    assert profile.name == "generic_espr_v1"
    assert [item.value for item in profile.allowed_carrier_types] == ["qr", "datamatrix", "rfid"]
    assert [item.value for item in profile.allowed_identifier_schemes] == [
        "gs1_gtin",
        "gs1_epc_tds23",
        "iec61406",
        "direct_url",
    ]
    assert [item.value for item in profile.publish_allowed_statuses] == ["active"]
    assert profile.publish_require_active_carrier is True
    assert profile.enforce_gtin_verified is True


def test_parse_invalid_profile_payload_falls_back_to_default() -> None:
    profile = parse_data_carrier_compliance_profile({"name": 123, "allowed_carrier_types": "qr"})
    assert profile == default_data_carrier_compliance_profile()


def test_profile_dedupes_list_values() -> None:
    profile = DataCarrierComplianceProfile.model_validate(
        {
            "allowed_carrier_types": ["qr", "qr", "datamatrix"],
            "allowed_identifier_schemes": ["gs1_gtin", "gs1_gtin", "direct_url"],
            "publish_allowed_statuses": ["active", "active"],
        }
    )
    assert [item.value for item in profile.allowed_carrier_types] == ["qr", "datamatrix"]
    assert [item.value for item in profile.allowed_identifier_schemes] == [
        "gs1_gtin",
        "direct_url",
    ]
    assert [item.value for item in profile.publish_allowed_statuses] == ["active"]
