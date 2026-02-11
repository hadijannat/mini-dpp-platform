"""Inspection regression checks for AASX round-trip compliance tooling."""

from __future__ import annotations

from tests.tools.aasx_roundtrip_validator import roundtrip_validate


def test_builtin_roundtrip_validator_passes() -> None:
    """Built-in AAS environment should survive object-store/AASX round-trip."""
    report = roundtrip_validate(
        {
            "assetAdministrationShells": [
                {
                    "modelType": "AssetAdministrationShell",
                    "id": "urn:test:aas:cf",
                    "idShort": "CFInspectionAAS",
                    "assetInformation": {
                        "assetKind": "Instance",
                        "globalAssetId": "urn:test:asset:cf",
                    },
                }
            ],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:test:sm:cf",
                    "idShort": "CarbonFootprint",
                    "semanticId": {
                        "type": "ExternalReference",
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0",
                            }
                        ],
                    },
                    "submodelElements": [
                        {
                            "modelType": "Property",
                            "idShort": "PcfValue",
                            "valueType": "xs:double",
                            "value": "12.4",
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
    )
    assert report["passed"], report
    assert report["steps"]["store_to_aasx"]["structure_valid"] is True
    assert report["steps"]["id_comparison"]["missing_after_roundtrip"] == []

