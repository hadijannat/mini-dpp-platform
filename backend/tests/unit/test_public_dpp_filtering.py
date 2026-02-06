"""
Unit tests for public DPP element filtering.

Verifies that confidential elements are stripped from public API responses
while public elements (including those with no qualifier) pass through.
"""

from __future__ import annotations

from app.modules.dpps.public_router import _element_is_public, _filter_public_aas_environment


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
