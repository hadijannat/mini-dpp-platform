"""
Unit tests for public DPP element filtering.

Verifies that confidential elements are stripped from public API responses
while public elements (including those with no qualifier) pass through.
"""

from __future__ import annotations

from app.modules.dpps.public_router import (
    _element_is_public,
    _filter_public_aas_environment,
    _filter_public_asset_ids,
)


def test_element_without_qualifier_treated_as_public() -> None:
    """Elements with no qualifiers are treated as public by default."""
    element: dict = {"idShort": "ManufacturerName", "value": "ACME Corp"}
    assert _element_is_public(element) is True


def test_element_with_public_qualifier_is_public() -> None:
    """Elements with Confidentiality=public pass through."""
    element: dict = {
        "idShort": "ManufacturerName",
        "value": "ACME Corp",
        "qualifiers": [{"type": "Confidentiality", "value": "public"}],
    }
    assert _element_is_public(element) is True


def test_element_with_confidential_qualifier_is_not_public() -> None:
    """Elements with Confidentiality=confidential are filtered out."""
    element: dict = {
        "idShort": "InternalCost",
        "value": "1234.56",
        "qualifiers": [{"type": "Confidentiality", "value": "confidential"}],
    }
    assert _element_is_public(element) is False


def test_element_with_private_qualifier_is_not_public() -> None:
    """Elements with Confidentiality=private are filtered out."""
    element: dict = {
        "idShort": "SecretFormula",
        "value": "xyz",
        "qualifiers": [{"type": "Confidentiality", "value": "Private"}],
    }
    assert _element_is_public(element) is False


def test_filter_removes_confidential_elements() -> None:
    """_filter_public_aas_environment strips confidential elements from submodels."""
    aas_env: dict = {
        "submodels": [
            {
                "idShort": "Nameplate",
                "submodelElements": [
                    {"idShort": "ManufacturerName", "value": "ACME"},
                    {
                        "idShort": "InternalCost",
                        "value": "9999",
                        "qualifiers": [{"type": "Confidentiality", "value": "confidential"}],
                    },
                    {
                        "idShort": "SerialNumber",
                        "value": "SN-001",
                        "qualifiers": [{"type": "Confidentiality", "value": "public"}],
                    },
                ],
            }
        ]
    }

    filtered = _filter_public_aas_environment(aas_env)
    elements = filtered["submodels"][0]["submodelElements"]
    id_shorts = [el["idShort"] for el in elements]
    assert "ManufacturerName" in id_shorts
    assert "SerialNumber" in id_shorts
    assert "InternalCost" not in id_shorts


def test_filter_returns_all_public_elements() -> None:
    """When all elements are public, all are returned."""
    aas_env: dict = {
        "submodels": [
            {
                "idShort": "Nameplate",
                "submodelElements": [
                    {"idShort": "ManufacturerName", "value": "ACME"},
                    {"idShort": "SerialNumber", "value": "SN-001"},
                ],
            }
        ]
    }
    filtered = _filter_public_aas_environment(aas_env)
    assert len(filtered["submodels"][0]["submodelElements"]) == 2


def test_filter_does_not_mutate_original() -> None:
    """Filtering creates a deep copy; original is untouched."""
    aas_env: dict = {
        "submodels": [
            {
                "idShort": "Nameplate",
                "submodelElements": [
                    {"idShort": "ManufacturerName", "value": "ACME"},
                    {
                        "idShort": "Secret",
                        "value": "hidden",
                        "qualifiers": [{"type": "Confidentiality", "value": "confidential"}],
                    },
                ],
            }
        ]
    }
    _filter_public_aas_environment(aas_env)
    assert len(aas_env["submodels"][0]["submodelElements"]) == 2


def test_filter_removes_confidential_nested_elements() -> None:
    """Nested confidential elements are removed recursively."""
    aas_env: dict = {
        "submodels": [
            {
                "idShort": "Nameplate",
                "submodelElements": [
                    {
                        "idShort": "OuterCollection",
                        "modelType": "SubmodelElementCollection",
                        "value": [
                            {
                                "idShort": "PublicInner",
                                "value": "ok",
                            },
                            {
                                "idShort": "SecretInner",
                                "value": "hidden",
                                "qualifiers": [{"type": "Confidentiality", "value": "confidential"}],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    filtered = _filter_public_aas_environment(aas_env)
    nested_values = filtered["submodels"][0]["submodelElements"][0]["value"]
    id_shorts = [entry["idShort"] for entry in nested_values]
    assert "PublicInner" in id_shorts
    assert "SecretInner" not in id_shorts


def test_filter_removes_sensitive_public_keys_from_aas_environment() -> None:
    """Sensitive keys are dropped from public AAS payloads as guardrails."""
    aas_env: dict = {
        "submodels": [
            {
                "idShort": "Nameplate",
                "submodelElements": [
                    {"idShort": "ManufacturerName", "value": "ACME"},
                ],
            }
        ],
        "payload": {"secret": "should-not-leak"},
        "owner_subject": "user-123",
        "read_point": "line-7",
    }
    filtered = _filter_public_aas_environment(aas_env)
    assert "payload" not in filtered
    assert "owner_subject" not in filtered
    assert "read_point" not in filtered


def test_filter_public_asset_ids_removes_sensitive_identifiers() -> None:
    asset_ids = {
        "manufacturerPartId": "PART-001",
        "serialNumber": "SN-SECRET",
        "batchId": "BATCH-SECRET",
        "globalAssetId": "urn:asset:secret",
        "customSafeCode": "SAFE-123",
    }
    filtered = _filter_public_asset_ids(asset_ids)
    assert filtered == {
        "manufacturerPartId": "PART-001",
        "customSafeCode": "SAFE-123",
    }
