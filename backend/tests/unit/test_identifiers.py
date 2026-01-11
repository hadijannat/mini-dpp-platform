import pytest

from app.core.identifiers import (
    IdentifierValidationError,
    build_composite_suffix,
    build_global_asset_id,
    normalize_base_uri,
)


def test_normalize_base_uri_adds_trailing_slash() -> None:
    assert normalize_base_uri("http://example.org/asset") == "http://example.org/asset/"


def test_normalize_base_uri_rejects_https() -> None:
    with pytest.raises(IdentifierValidationError):
        normalize_base_uri("https://example.org/asset/")


def test_normalize_base_uri_rejects_query_and_fragment() -> None:
    with pytest.raises(IdentifierValidationError):
        normalize_base_uri("http://example.org/asset/?x=1")
    with pytest.raises(IdentifierValidationError):
        normalize_base_uri("http://example.org/asset/#hash")


def test_build_composite_suffix_includes_serial_and_batch() -> None:
    asset_ids = {
        "manufacturerPartId": "PART-123",
        "serialNumber": "SN/456",
        "batchId": "B#789",
    }
    assert build_composite_suffix(asset_ids) == "PART-123--SN%2F456--B%23789"


def test_build_global_asset_id_uses_normalized_base() -> None:
    asset_ids = {"manufacturerPartId": "PART-123", "serialNumber": "SN-456"}
    result = build_global_asset_id("http://example.org/asset", asset_ids)
    assert result == "http://example.org/asset/PART-123--SN-456"
