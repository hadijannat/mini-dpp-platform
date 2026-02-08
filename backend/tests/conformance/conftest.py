"""Shared fixtures for AAS conformance tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture()
def minimal_aas_env() -> dict[str, Any]:
    """Return a minimal AAS environment that is metamodel-conformant."""
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:aas:conformance:1",
                "idShort": "ConformanceAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:conformance:1",
                },
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:conformance:1",
                "idShort": "ConformanceSubmodel",
                "submodelElements": [
                    {
                        "modelType": "Property",
                        "idShort": "TestProperty",
                        "valueType": "xs:string",
                        "value": "hello",
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }
