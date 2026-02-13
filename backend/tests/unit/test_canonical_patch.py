from __future__ import annotations

import pytest

from app.modules.dpps.canonical_patch import apply_canonical_patch
from app.modules.dpps.idshort_factory import generate_next_id_short


def _contract(read_only: bool = False) -> dict:
    return {
        "definition": {
            "submodel": {
                "idShort": "Nameplate",
                "elements": [
                    {
                        "idShort": "ManufacturerName",
                        "modelType": "Property",
                        "smt": {"access_mode": "ReadOnly" if read_only else "Read/Write"},
                    },
                    {
                        "idShort": "ProductDesignation",
                        "modelType": "MultiLanguageProperty",
                        "smt": {},
                    },
                    {
                        "idShort": "Manual",
                        "modelType": "File",
                        "smt": {},
                    },
                    {
                        "idShort": "Materials",
                        "modelType": "SubmodelElementList",
                        "smt": {"cardinality": "OneToMany", "naming": r"Material\d{2}"},
                        "items": {
                            "idShort": "Material{00}",
                            "modelType": "SubmodelElementCollection",
                            "children": [
                                {"idShort": "Name", "modelType": "Property", "smt": {}},
                            ],
                        },
                    },
                ],
            }
        }
    }


def _env() -> dict:
    return {
        "assetAdministrationShells": [],
        "conceptDescriptions": [],
        "submodels": [
            {
                "id": "urn:sm:1",
                "idShort": "Nameplate",
                "submodelElements": [
                    {
                        "modelType": "Property",
                        "idShort": "ManufacturerName",
                        "valueType": "xs:string",
                        "value": "Old Manufacturer",
                        "qualifiers": [{"type": "Custom", "value": "keep-me"}],
                    },
                    {
                        "modelType": "MultiLanguageProperty",
                        "idShort": "ProductDesignation",
                        "value": [{"language": "en", "text": "Pump"}],
                    },
                    {
                        "modelType": "File",
                        "idShort": "Manual",
                        "contentType": "application/pdf",
                        "value": "/aasx/files/manual.pdf",
                    },
                    {
                        "modelType": "SubmodelElementList",
                        "idShort": "Materials",
                        "value": [
                            {
                                "modelType": "SubmodelElementCollection",
                                "idShort": "Material01",
                                "value": [
                                    {
                                        "modelType": "Property",
                                        "idShort": "Name",
                                        "valueType": "xs:string",
                                        "value": "Steel",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ],
    }


def test_generate_next_id_short_prefers_placeholder_pattern() -> None:
    assert generate_next_id_short("Material{00}", ["Material01", "Material02"]) == "Material03"


def test_apply_canonical_patch_updates_values_and_preserves_metadata() -> None:
    result = apply_canonical_patch(
        aas_env_json=_env(),
        submodel_id="urn:sm:1",
        operations=[
            {"op": "set_value", "path": "ManufacturerName", "value": "New Manufacturer"},
            {
                "op": "set_multilang",
                "path": "ProductDesignation",
                "value": {"en": "Pump", "de": "Pumpe"},
            },
            {
                "op": "set_file_ref",
                "path": "Manual",
                "value": {"contentType": "application/pdf", "url": "https://cdn/manual.pdf"},
            },
            {"op": "add_list_item", "path": "Materials", "value": {"Name": "Copper"}},
        ],
        contract=_contract(),
        strict=True,
    )

    submodel = result.aas_env_json["submodels"][0]
    elements = {entry["idShort"]: entry for entry in submodel["submodelElements"]}

    assert elements["ManufacturerName"]["value"] == "New Manufacturer"
    assert elements["ManufacturerName"]["qualifiers"] == [{"type": "Custom", "value": "keep-me"}]
    assert elements["ProductDesignation"]["value"] == [
        {"language": "de", "text": "Pumpe"},
        {"language": "en", "text": "Pump"},
    ]
    assert elements["Manual"]["value"] == "https://cdn/manual.pdf"
    materials = elements["Materials"]["value"]
    assert len(materials) == 2
    assert materials[1]["idShort"] == "Material02"


def test_apply_canonical_patch_blocks_read_only_nodes() -> None:
    with pytest.raises(ValueError, match="ReadOnly"):
        apply_canonical_patch(
            aas_env_json=_env(),
            submodel_id="urn:sm:1",
            operations=[{"op": "set_value", "path": "ManufacturerName", "value": "Blocked"}],
            contract=_contract(read_only=True),
            strict=True,
        )


def test_apply_canonical_patch_enforces_one_to_many_minimum() -> None:
    with pytest.raises(ValueError, match="requires at least one list item"):
        apply_canonical_patch(
            aas_env_json=_env(),
            submodel_id="urn:sm:1",
            operations=[{"op": "remove_list_item", "path": "Materials", "index": 0}],
            contract=_contract(),
            strict=True,
        )
