"""Inspection checks for SMT qualifier projection into UI schema."""

from __future__ import annotations

from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter


def test_schema_includes_dynamic_id_short_constraints() -> None:
    converter = DefinitionToSchemaConverter()
    definition = {
        "submodel": {
            "idShort": "CarbonFootprint",
            "elements": [
                {
                    "idShort": "ProductCarbonFootprint",
                    "modelType": "SubmodelElementList",
                    "smt": {
                        "cardinality": "OneToMany",
                        "allowed_id_short": ["PCF{00}", "PCF{01}"],
                        "edit_id_short": False,
                        "naming": "idShort",
                    },
                    "items": {
                        "modelType": "SubmodelElementCollection",
                        "children": [
                            {
                                "idShort": "DeclaredValue",
                                "modelType": "Property",
                                "valueType": "xs:double",
                                "smt": {},
                            }
                        ],
                        "smt": {},
                    },
                }
            ],
        }
    }

    schema = converter.convert(definition)
    list_schema = schema["properties"]["ProductCarbonFootprint"]

    assert list_schema["type"] == "array"
    assert list_schema["minItems"] == 1
    assert list_schema["x-allowed-id-short"] == ["PCF{00}", "PCF{01}"]
    assert list_schema["x-edit-id-short"] is False
    assert list_schema["x-naming"] == "idShort"


def test_schema_emits_either_or_and_required_languages() -> None:
    converter = DefinitionToSchemaConverter()
    definition = {
        "submodel": {
            "idShort": "CarbonFootprint",
            "elements": [
                {
                    "idShort": "DeclaredMethod",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "smt": {"either_or": "method_or_api"},
                },
                {
                    "idShort": "ExternalMethodDescription",
                    "modelType": "MultiLanguageProperty",
                    "smt": {
                        "either_or": "method_or_api",
                        "required_lang": ["en", "de"],
                    },
                },
            ],
        }
    }

    schema = converter.convert(definition)
    method_schema = schema["properties"]["DeclaredMethod"]
    description_schema = schema["properties"]["ExternalMethodDescription"]

    assert method_schema["x-either-or"] == "method_or_api"
    assert description_schema["x-either-or"] == "method_or_api"
    assert description_schema["x-required-languages"] == ["de", "en"]

