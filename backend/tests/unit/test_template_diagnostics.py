from app.modules.templates.diagnostics import find_schema_missing_paths


def test_find_schema_missing_paths_handles_lists() -> None:
    definition = {
        "template_key": "demo",
        "submodel": {
            "idShort": "Root",
            "elements": [
                {
                    "path": "Root/Items",
                    "idShort": "Items",
                    "modelType": "SubmodelElementList",
                    "items": {
                        "path": "Root/Items[]/Name",
                        "idShort": "Name",
                        "modelType": "Property",
                    },
                }
            ],
        },
    }

    schema = {
        "type": "object",
        "properties": {
            "Items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "Name": {"type": "string"},
                    },
                },
            }
        },
    }

    missing = find_schema_missing_paths(definition, schema)
    assert missing == []


def test_find_schema_missing_paths_reports_missing() -> None:
    definition = {
        "template_key": "demo",
        "submodel": {
            "idShort": "Root",
            "elements": [
                {
                    "path": "Root/Expected",
                    "idShort": "Expected",
                    "modelType": "Property",
                }
            ],
        },
    }

    schema = {"type": "object", "properties": {}}
    missing = find_schema_missing_paths(definition, schema)
    assert missing == ["Root/Expected"]
