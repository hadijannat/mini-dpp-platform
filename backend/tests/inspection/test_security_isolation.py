"""Inspection checks for public/tier filtering behavior."""

from __future__ import annotations

from app.modules.dpps.public_router import _filter_public_aas_environment
from app.modules.dpps.submodel_filter import filter_aas_env_by_espr_tier


def _aas_env_fixture() -> dict:
    return {
        "submodels": [
            {
                "idShort": "CarbonFootprint",
                "semanticId": {
                    "keys": [
                        {
                            "value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0"
                        }
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "Property",
                        "idShort": "PublicPCF",
                        "value": "12.3",
                        "qualifiers": [{"type": "Confidentiality", "value": "public"}],
                    },
                    {
                        "modelType": "Property",
                        "idShort": "SupplierMargin",
                        "value": "4.2",
                        "qualifiers": [{"type": "Confidentiality", "value": "confidential"}],
                    },
                ],
            },
            {
                "idShort": "InternalOnly",
                "semanticId": {"keys": [{"value": "urn:internal:submodel"}]},
                "submodelElements": [],
            },
        ]
    }


def test_unknown_espr_tier_fails_closed() -> None:
    env = _aas_env_fixture()
    filtered = filter_aas_env_by_espr_tier(env, "unknown-tier")
    assert filtered["submodels"] == []


def test_consumer_tier_keeps_carbon_footprint_submodel() -> None:
    env = _aas_env_fixture()
    filtered = filter_aas_env_by_espr_tier(env, "consumer")

    assert len(filtered["submodels"]) == 1
    assert filtered["submodels"][0]["idShort"] == "CarbonFootprint"


def test_public_filter_removes_sensitive_keys_and_confidential_elements() -> None:
    env = {
        "asset_ids": {
            "manufacturerPartId": "PART-001",
            "serialNumber": "SN-DO-NOT-LEAK",
        },
        "submodels": _aas_env_fixture()["submodels"],
    }
    filtered = _filter_public_aas_environment(env)

    # Sensitive top-level key should be stripped by public filtering
    assert "serialNumber" not in str(filtered)
    # Confidential element should be removed
    elements = filtered["submodels"][0]["submodelElements"]
    id_shorts = [element["idShort"] for element in elements]
    assert "SupplierMargin" not in id_shorts
    assert "PublicPCF" in id_shorts

