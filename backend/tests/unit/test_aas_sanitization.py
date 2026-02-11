"""Unit tests for AAS list-item idShort sanitization."""

from __future__ import annotations

from app.modules.aas.sanitization import sanitize_submodel_list_item_id_shorts


def test_sanitize_removes_id_short_in_root_submodel_element_list() -> None:
    env = {
        "assetAdministrationShells": [],
        "submodels": [
            {
                "id": "urn:sm:1",
                "modelType": "Submodel",
                "submodelElements": [
                    {
                        "idShort": "Codes",
                        "modelType": "SubmodelElementList",
                        "value": [
                            {
                                "idShort": "generated_submodel_list_hack_1",
                                "modelType": "Property",
                                "valueType": "xs:string",
                                "value": "A",
                            }
                        ],
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }

    sanitized, stats = sanitize_submodel_list_item_id_shorts(env)

    assert "idShort" in env["submodels"][0]["submodelElements"][0]["value"][0]
    assert "idShort" not in sanitized["submodels"][0]["submodelElements"][0]["value"][0]
    assert stats.lists_scanned == 1
    assert stats.items_scanned == 1
    assert stats.idshort_removed == 1
    assert len(stats.paths_changed) == 1


def test_sanitize_handles_nested_lists() -> None:
    env = {
        "assetAdministrationShells": [],
        "submodels": [
            {
                "id": "urn:sm:2",
                "modelType": "Submodel",
                "submodelElements": [
                    {
                        "idShort": "Outer",
                        "modelType": "SubmodelElementCollection",
                        "value": [
                            {
                                "idShort": "InnerList",
                                "modelType": "SubmodelElementList",
                                "value": [
                                    {
                                        "idShort": "generated_submodel_list_hack_2",
                                        "modelType": "SubmodelElementCollection",
                                        "value": [
                                            {
                                                "idShort": "DeepList",
                                                "modelType": "SubmodelElementList",
                                                "value": [
                                                    {
                                                        "idShort": "generated_submodel_list_hack_3",
                                                        "modelType": "Property",
                                                        "valueType": "xs:string",
                                                        "value": "X",
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }

    sanitized, stats = sanitize_submodel_list_item_id_shorts(env)

    inner_item = sanitized["submodels"][0]["submodelElements"][0]["value"][0]["value"][0]
    deep_item = sanitized["submodels"][0]["submodelElements"][0]["value"][0]["value"][0]["value"][
        0
    ]["value"][0]
    assert "idShort" not in inner_item
    assert "idShort" not in deep_item
    assert stats.idshort_removed == 2
    assert stats.lists_scanned >= 2


def test_sanitize_leaves_non_list_id_short_untouched() -> None:
    env = {
        "assetAdministrationShells": [],
        "submodels": [
            {
                "id": "urn:sm:3",
                "modelType": "Submodel",
                "submodelElements": [
                    {
                        "idShort": "ManufacturerName",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "value": "ACME",
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }

    sanitized, stats = sanitize_submodel_list_item_id_shorts(env)

    assert sanitized["submodels"][0]["submodelElements"][0]["idShort"] == "ManufacturerName"
    assert stats.idshort_removed == 0
    assert stats.lists_scanned == 0
