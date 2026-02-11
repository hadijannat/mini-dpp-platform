"""Unit tests for Carbon Footprint-aware material inventory extraction."""

from __future__ import annotations

from app.modules.lca.extractor import extract_material_inventory


def test_extract_material_inventory_collects_external_pcf_api_refs() -> None:
    aas_env = {
        "submodels": [
            {
                "idShort": "CarbonFootprint",
                "semanticId": {
                    "keys": [
                        {"value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0"}
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementList",
                        "idShort": "ProductOrSectorSpecificCarbonFootprints",
                        "value": [
                            {
                                "modelType": "SubmodelElementCollection",
                                "idShort": None,
                                "value": [
                                    {
                                        "modelType": "SubmodelElementCollection",
                                        "idShort": "ExternalPcfApi",
                                        "value": [
                                            {
                                                "modelType": "Property",
                                                "idShort": "PcfApiEndpoint",
                                                "valueType": "xs:anyURI",
                                                "value": "https://pcf.example.com/api",
                                            },
                                            {
                                                "modelType": "Property",
                                                "idShort": "PcfApiQuery",
                                                "valueType": "xs:string",
                                                "value": "productId=123",
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }

    inventory = extract_material_inventory(aas_env)

    assert inventory.external_pcf_apis
    ref = inventory.external_pcf_apis[0]
    assert ref.endpoint == "https://pcf.example.com/api"
    assert ref.query == "productId=123"
    assert ref.source_submodel == "CarbonFootprint"


def test_extract_material_inventory_maps_material_to_declared_pcf() -> None:
    aas_env = {
        "submodels": [
            {
                "idShort": "BillOfMaterial",
                "semanticId": {
                    "keys": [
                        {"value": "https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel"}
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementCollection",
                        "idShort": "Component",
                        "value": [
                            {
                                "modelType": "Property",
                                "idShort": "MaterialName",
                                "valueType": "xs:string",
                                "value": "Steel",
                            },
                            {
                                "modelType": "Property",
                                "idShort": "Mass",
                                "valueType": "xs:double",
                                "value": "2.0",
                            },
                        ],
                    }
                ],
            },
            {
                "idShort": "CarbonFootprint",
                "semanticId": {
                    "keys": [
                        {"value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0"}
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementList",
                        "idShort": "ProductCarbonFootprint",
                        "value": [
                            {
                                "modelType": "SubmodelElementCollection",
                                "idShort": None,
                                "value": [
                                    {
                                        "modelType": "Property",
                                        "idShort": "MaterialName",
                                        "valueType": "xs:string",
                                        "value": "Steel",
                                    },
                                    {
                                        "modelType": "Property",
                                        "idShort": "PCF",
                                        "valueType": "xs:double",
                                        "value": "5.4",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
    }

    inventory = extract_material_inventory(aas_env)

    assert inventory.items
    item = inventory.items[0]
    assert item.material_name == "Steel"
    assert item.pre_declared_pcf == 5.4


def test_extract_material_inventory_handles_cf_list_entries_with_external_refs() -> None:
    aas_env = {
        "submodels": [
            {
                "idShort": "BillOfMaterial",
                "semanticId": {
                    "keys": [
                        {"value": "https://admin-shell.io/idta/HierarchicalStructures/1/1/Submodel"}
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementCollection",
                        "idShort": "Component",
                        "value": [
                            {
                                "modelType": "Property",
                                "idShort": "MaterialName",
                                "valueType": "xs:string",
                                "value": "Steel",
                            },
                            {
                                "modelType": "Property",
                                "idShort": "Mass",
                                "valueType": "xs:double",
                                "value": "1.0",
                            },
                        ],
                    },
                    {
                        "modelType": "SubmodelElementCollection",
                        "idShort": "Component",
                        "value": [
                            {
                                "modelType": "Property",
                                "idShort": "MaterialName",
                                "valueType": "xs:string",
                                "value": "Aluminum",
                            },
                            {
                                "modelType": "Property",
                                "idShort": "Mass",
                                "valueType": "xs:double",
                                "value": "1.0",
                            },
                        ],
                    },
                ],
            },
            {
                "idShort": "CarbonFootprint",
                "semanticId": {
                    "keys": [
                        {"value": "https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0"}
                    ]
                },
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementList",
                        "idShort": "ProductCarbonFootprint",
                        "value": [
                            {
                                "modelType": "SubmodelElementCollection",
                                "idShort": None,
                                "value": [
                                    {
                                        "modelType": "Property",
                                        "idShort": "MaterialName",
                                        "valueType": "xs:string",
                                        "value": "Steel",
                                    },
                                    {
                                        "modelType": "Property",
                                        "idShort": "PCF",
                                        "valueType": "xs:double",
                                        "value": "5.4",
                                    },
                                    {
                                        "modelType": "SubmodelElementCollection",
                                        "idShort": "ExternalPcfApi",
                                        "value": [
                                            {
                                                "modelType": "Property",
                                                "idShort": "PcfApiEndpoint",
                                                "valueType": "xs:anyURI",
                                                "value": "https://pcf.example.com/api",
                                            },
                                            {
                                                "modelType": "Property",
                                                "idShort": "PcfApiQuery",
                                                "valueType": "xs:string",
                                                "value": "productId=steel",
                                            },
                                        ],
                                    },
                                ],
                            },
                            {
                                "modelType": "SubmodelElementCollection",
                                "idShort": None,
                                "value": [
                                    {
                                        "modelType": "Property",
                                        "idShort": "MaterialName",
                                        "valueType": "xs:string",
                                        "value": "Aluminum",
                                    },
                                    {
                                        "modelType": "Property",
                                        "idShort": "PCF",
                                        "valueType": "xs:double",
                                        "value": "3.1",
                                    },
                                ],
                            },
                        ],
                    }
                ],
            },
        ]
    }

    inventory = extract_material_inventory(aas_env)

    by_name = {item.material_name: item for item in inventory.items}
    assert by_name["Steel"].pre_declared_pcf == 5.4
    assert by_name["Aluminum"].pre_declared_pcf == 3.1

    assert len(inventory.external_pcf_apis) == 1
    api_ref = inventory.external_pcf_apis[0]
    assert api_ref.endpoint == "https://pcf.example.com/api"
    assert api_ref.query == "productId=steel"
    assert api_ref.source_path == "CarbonFootprint/ProductCarbonFootprint[0]/ExternalPcfApi"
