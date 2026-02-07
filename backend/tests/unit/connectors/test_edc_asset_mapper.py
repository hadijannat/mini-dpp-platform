"""Unit tests for EDC asset mapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

from app.modules.connectors.edc.asset_mapper import map_dpp_to_edc_asset


def _make_dpp(
    dpp_id: str = "00000000-0000-0000-0000-000000000001",
    manufacturer_part_id: str = "PART-001",
    serial_number: str = "SN-12345",
) -> MagicMock:
    dpp = MagicMock()
    dpp.id = UUID(dpp_id)
    dpp.asset_ids = {
        "manufacturerPartId": manufacturer_part_id,
        "serialNumber": serial_number,
        "globalAssetId": f"urn:uuid:{dpp_id}",
    }
    return dpp


def _make_revision(
    revision_no: int = 1,
    submodels: list[dict[str, Any]] | None = None,
) -> MagicMock:
    if submodels is None:
        submodels = [
            {
                "id": "urn:dpp:sm:nameplate:PART-001",
                "idShort": "Nameplate",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
                        }
                    ],
                },
                "submodelElements": [],
            }
        ]
    revision = MagicMock()
    revision.revision_no = revision_no
    revision.aas_env_json = {
        "assetAdministrationShells": [],
        "submodels": submodels,
        "conceptDescriptions": [],
    }
    return revision


class TestMapDppToEdcAsset:
    def test_asset_id_format(self) -> None:
        dpp = _make_dpp()
        revision = _make_revision()

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public")

        assert asset.asset_id == f"dpp-{dpp.id}"

    def test_data_address_points_to_public_api(self) -> None:
        dpp = _make_dpp()
        revision = _make_revision()

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public")

        assert f"/dpps/{dpp.id}" in asset.data_address.base_url
        assert asset.data_address.type == "HttpData"

    def test_properties_contain_dpp_metadata(self) -> None:
        dpp = _make_dpp(manufacturer_part_id="WIDGET-42", serial_number="SN-999")
        revision = _make_revision()

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public")

        assert "WIDGET-42" in asset.properties["name"]
        assert "SN-999" in asset.properties["name"]
        assert asset.properties["dpp:manufacturerPartId"] == "WIDGET-42"
        assert asset.properties["contenttype"] == "application/json"

    def test_semantic_ids_collected(self) -> None:
        dpp = _make_dpp()
        revision = _make_revision(
            submodels=[
                {
                    "id": "urn:sm:1",
                    "idShort": "Nameplate",
                    "semanticId": {
                        "type": "ExternalReference",
                        "keys": [
                            {
                                "type": "GlobalReference",
                                "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
                            }
                        ],
                    },
                },
                {
                    "id": "urn:sm:2",
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
                },
            ]
        )

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public")

        assert len(asset.properties["dpp:semanticIds"]) == 2
        assert len(asset.properties["dpp:submodelIdShorts"]) == 2
        assert "Nameplate" in asset.properties["dpp:submodelIdShorts"]
        assert "CarbonFootprint" in asset.properties["dpp:submodelIdShorts"]

    def test_trailing_slash_in_base_url(self) -> None:
        dpp = _make_dpp()
        revision = _make_revision()

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public/")

        # Should not produce double slashes
        assert "//dpps" not in asset.data_address.base_url

    def test_edc_payload_serialization(self) -> None:
        dpp = _make_dpp()
        revision = _make_revision()

        asset = map_dpp_to_edc_asset(dpp, revision, "https://dpp.dev/api/v1/public")
        payload = asset.to_edc_payload()

        assert "@id" in payload
        assert "dataAddress" in payload
        assert payload["dataAddress"]["@type"] == "DataAddress"
