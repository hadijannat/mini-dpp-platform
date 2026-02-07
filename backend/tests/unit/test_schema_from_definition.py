from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter


def test_definition_to_schema_is_deterministic() -> None:
    definition = {
        "submodel": {
            "idShort": "Demo",
            "description": {"en": "Demo submodel"},
            "elements": [
                {
                    "idShort": "B",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "smt": {},
                },
                {
                    "idShort": "A",
                    "modelType": "Property",
                    "valueType": "xs:integer",
                    "smt": {"allowed_range": {"min": 1, "max": 5, "raw": "1..5"}},
                },
            ],
        }
    }

    converter = DefinitionToSchemaConverter()

    first = converter.convert(definition)
    second = converter.convert(definition)

    assert first == second
    assert list(first["properties"].keys()) == ["A", "B"]
    assert first["properties"]["A"]["minimum"] == 1
    assert first["properties"]["A"]["maximum"] == 5
