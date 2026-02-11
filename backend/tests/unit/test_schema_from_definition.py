"""Comprehensive tests for DefinitionToSchemaConverter.

Covers all 12 AAS element types, SMT qualifier mappings,
value coercion, text picking, cardinality/required logic,
and edge cases (empty/malformed definitions).
"""

import pytest

from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter


@pytest.fixture
def converter() -> DefinitionToSchemaConverter:
    return DefinitionToSchemaConverter()


# ---------------------------------------------------------------------------
# Determinism & sorting
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# AAS element types
# ---------------------------------------------------------------------------


class TestProperty:
    def test_string_property(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Name",
            "modelType": "Property",
            "valueType": "xs:string",
            "description": {"en": "A name"},
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "string"
        assert schema["title"] == "Name"
        assert schema["description"] == "A name"

    def test_integer_property(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Count",
            "modelType": "Property",
            "valueType": "xs:integer",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "integer"

    def test_boolean_property(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Active",
            "modelType": "Property",
            "valueType": "xs:boolean",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "boolean"

    def test_double_property(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Weight",
            "modelType": "Property",
            "valueType": "xs:double",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "number"

    def test_date_property_has_format(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "MfgDate",
            "modelType": "Property",
            "valueType": "xs:date",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "string"
        assert schema["format"] == "date"

    def test_datetime_property_has_format(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Timestamp",
            "modelType": "Property",
            "valueType": "xs:dateTime",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["format"] == "date-time"

    def test_uri_property_has_format(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Link",
            "modelType": "Property",
            "valueType": "xs:anyURI",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["format"] == "uri"

    def test_semantic_id_passthrough(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Foo",
            "modelType": "Property",
            "valueType": "xs:string",
            "semanticId": "urn:example:Foo",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-semantic-id"] == "urn:example:Foo"

    def test_unknown_value_type_defaults_to_string(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Exotic",
            "modelType": "Property",
            "valueType": "xs:unsupported",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "string"


class TestSubmodelElementCollection:
    def test_nested_collection(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "ContactInfo",
            "modelType": "SubmodelElementCollection",
            "description": {"en": "Contact details"},
            "children": [
                {
                    "idShort": "Phone",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "smt": {"cardinality": "One"},
                },
                {
                    "idShort": "Email",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "smt": {},
                },
            ],
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["title"] == "ContactInfo"
        assert "Email" in schema["properties"]
        assert "Phone" in schema["properties"]
        assert schema["required"] == ["Phone"]

    def test_empty_collection(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Empty",
            "modelType": "SubmodelElementCollection",
            "children": [],
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["properties"] == {}

    def test_children_without_id_short_are_skipped(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Partial",
            "modelType": "SubmodelElementCollection",
            "children": [
                {"modelType": "Property", "valueType": "xs:string", "smt": {}},
                {
                    "idShort": "Valid",
                    "modelType": "Property",
                    "valueType": "xs:string",
                    "smt": {},
                },
            ],
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert list(schema["properties"].keys()) == ["Valid"]


class TestSubmodelElementList:
    def test_list_with_item_template(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Materials",
            "modelType": "SubmodelElementList",
            "description": {"en": "Bill of materials"},
            "items": {
                "idShort": "Material",
                "modelType": "Property",
                "valueType": "xs:string",
                "smt": {},
            },
            "smt": {"cardinality": "OneToMany"},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "array"
        assert schema["title"] == "Materials"
        assert schema["minItems"] == 1
        assert schema["items"]["type"] == "string"

    def test_list_zero_to_many(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Tags",
            "modelType": "SubmodelElementList",
            "items": {
                "idShort": "Tag",
                "modelType": "Property",
                "valueType": "xs:string",
                "smt": {},
            },
            "smt": {"cardinality": "ZeroToMany"},
        }
        schema = converter._node_to_schema(node)
        assert schema["minItems"] == 0

    def test_list_without_items_defaults_to_string(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Bare",
            "modelType": "SubmodelElementList",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["items"] == {"type": "string"}

    def test_list_collection_without_item_definition_is_annotated_as_unresolved(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "AddressInformation",
            "modelType": "SubmodelElementList",
            "typeValueListElement": "SubmodelElementCollection",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "array"
        assert schema["x-unresolved-definition"] is True
        assert schema["items"]["x-unresolved-definition"] is True
        assert schema["items"]["x-unresolved-reason"] == "list_item_collection_definition_missing"


class TestMultiLanguageProperty:
    def test_multi_language_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "ProductName",
            "modelType": "MultiLanguageProperty",
            "description": {"en": "Product name in multiple languages"},
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["x-multi-language"] is True
        assert schema["additionalProperties"] == {"type": "string"}


class TestRange:
    def test_range_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Temperature",
            "modelType": "Range",
            "description": {"en": "Operating temperature"},
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["x-range"] is True
        assert "min" in schema["properties"]
        assert "max" in schema["properties"]


class TestFile:
    def test_file_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Manual",
            "modelType": "File",
            "description": {"en": "Product manual"},
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["x-file-upload"] is True
        assert "contentType" in schema["properties"]
        assert "pattern" in schema["properties"]["contentType"]
        assert schema["properties"]["value"]["format"] == "uri"
        assert "image/png" in schema["x-file-content-type-suggestions"]
        assert "application/pdf" in schema["x-file-content-type-suggestions"]


class TestBlob:
    def test_blob_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Image",
            "modelType": "Blob",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["x-blob"] is True
        assert schema["x-readonly"] is True
        assert schema["properties"]["value"]["contentEncoding"] == "base64"


class TestReferenceElement:
    def test_reference_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "DerivedFrom",
            "modelType": "ReferenceElement",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-reference"] is True
        assert schema["properties"]["type"]["enum"] == [
            "ModelReference",
            "ExternalReference",
        ]
        assert schema["properties"]["keys"]["type"] == "array"


class TestEntity:
    def test_entity_with_statements(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Component",
            "modelType": "Entity",
            "description": {"en": "A BOM component"},
            "statements": [
                {
                    "idShort": "Weight",
                    "modelType": "Property",
                    "valueType": "xs:double",
                    "smt": {},
                },
            ],
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-entity"] is True
        assert "entityType" in schema["properties"]
        assert schema["properties"]["entityType"]["enum"] == [
            "SelfManagedEntity",
            "CoManagedEntity",
        ]
        assert "globalAssetId" in schema["properties"]
        statements = schema["properties"]["statements"]
        assert "Weight" in statements["properties"]

    def test_entity_without_statements(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Bare",
            "modelType": "Entity",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["properties"]["statements"]["properties"] == {}


class TestRelationshipElement:
    def test_relationship_schema(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "IsPartOf",
            "modelType": "RelationshipElement",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-relationship"] is True
        assert schema["properties"]["first"]["x-reference"] is True
        assert schema["properties"]["second"]["x-reference"] is True


class TestAnnotatedRelationshipElement:
    def test_annotated_relationship_with_annotations(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "AssemblyLink",
            "modelType": "AnnotatedRelationshipElement",
            "annotations": [
                {
                    "idShort": "Confidence",
                    "modelType": "Property",
                    "valueType": "xs:double",
                    "smt": {},
                },
            ],
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-annotated-relationship"] is True
        assert "first" in schema["properties"]
        assert "second" in schema["properties"]
        annotations = schema["properties"]["annotations"]
        assert "Confidence" in annotations["properties"]

    def test_annotated_relationship_empty_annotations(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Link",
            "modelType": "AnnotatedRelationshipElement",
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["properties"]["annotations"]["properties"] == {}


class TestUnknownModelType:
    def test_unknown_type_produces_readonly_object(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "FutureType",
            "modelType": "SomeNewType",
            "description": {"en": "Unknown"},
            "smt": {},
        }
        schema = converter._node_to_schema(node)
        assert schema["type"] == "object"
        assert schema["x-readonly"] is True
        assert schema["title"] == "FutureType"


# ---------------------------------------------------------------------------
# SMT qualifier mappings (_apply_smt)
# ---------------------------------------------------------------------------


class TestApplySMT:
    def test_form_title_overrides_title(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Raw",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"form_title": "Pretty Title"},
        }
        schema = converter._node_to_schema(node)
        assert schema["title"] == "Pretty Title"
        assert schema["x-form-title"] == "Pretty Title"

    def test_form_info_sets_description(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Field",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"form_info": "Helpful hint"},
        }
        schema = converter._node_to_schema(node)
        assert schema["description"] == "Helpful hint"
        assert schema["x-form-info"] == "Helpful hint"

    def test_form_info_does_not_override_existing_description(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Field",
            "modelType": "Property",
            "valueType": "xs:string",
            "description": {"en": "Original"},
            "smt": {"form_info": "Extra"},
        }
        schema = converter._node_to_schema(node)
        assert schema["description"] == "Original"
        assert schema["x-form-info"] == "Extra"

    def test_form_url(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Field",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"form_url": "https://example.com/help"},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-form-url"] == "https://example.com/help"

    def test_form_choices_sets_enum_on_string(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Color",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"form_choices": ["Red", "Green", "Blue"]},
        }
        schema = converter._node_to_schema(node)
        assert schema["enum"] == ["Red", "Green", "Blue"]
        assert schema["x-form-choices"] == ["Red", "Green", "Blue"]

    def test_form_choices_does_not_set_enum_on_integer(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {
            "idShort": "Level",
            "modelType": "Property",
            "valueType": "xs:integer",
            "smt": {"form_choices": ["1", "2", "3"]},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-form-choices"] == ["1", "2", "3"]
        assert "enum" not in schema

    def test_default_value_coerced(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Qty",
            "modelType": "Property",
            "valueType": "xs:integer",
            "smt": {"default_value": "10"},
        }
        schema = converter._node_to_schema(node)
        assert schema["default"] == 10

    def test_example_value_coerced(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Price",
            "modelType": "Property",
            "valueType": "xs:double",
            "smt": {"example_value": "99.5"},
        }
        schema = converter._node_to_schema(node)
        assert schema["examples"] == [99.5]

    def test_allowed_value_regex(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Code",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"allowed_value_regex": r"^[A-Z]{3}\d{4}$"},
        }
        schema = converter._node_to_schema(node)
        assert schema["pattern"] == r"^[A-Z]{3}\d{4}$"
        assert schema["x-allowed-value"] == r"^[A-Z]{3}\d{4}$"

    def test_allowed_range_dict(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Temp",
            "modelType": "Property",
            "valueType": "xs:integer",
            "smt": {"allowed_range": {"min": -40, "max": 85, "raw": "-40..85"}},
        }
        schema = converter._node_to_schema(node)
        assert schema["minimum"] == -40.0
        assert schema["maximum"] == 85.0

    def test_allowed_range_string_fallback(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "X",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"allowed_range": "open-ended"},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-allowed-range"] == "open-ended"

    def test_required_lang(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Desc",
            "modelType": "MultiLanguageProperty",
            "smt": {"required_lang": ["de", "en", "en"]},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-required-languages"] == ["de", "en"]

    def test_either_or(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "F",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"either_or": "groupA"},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-either-or"] == "groupA"

    def test_access_mode_readonly(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Serial",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"access_mode": "readonly"},
        }
        schema = converter._node_to_schema(node)
        assert schema["readOnly"] is True
        assert schema["x-readonly"] is True

    def test_access_mode_writeonly(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Secret",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"access_mode": "write-only"},
        }
        schema = converter._node_to_schema(node)
        assert schema["writeOnly"] is True
        assert "readOnly" not in schema

    def test_allowed_id_short(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Dyn",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"allowed_id_short": ["Name{00}", "Name{01}"]},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-allowed-id-short"] == ["Name{00}", "Name{01}"]

    def test_edit_id_short(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Custom",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"edit_id_short": True},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-edit-id-short"] is True

    def test_naming(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Entry",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"naming": "dynamic"},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-naming"] == "dynamic"

    def test_cardinality_annotation(self, converter: DefinitionToSchemaConverter) -> None:
        node = {
            "idShort": "Item",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {"cardinality": "ZeroToOne"},
        }
        schema = converter._node_to_schema(node)
        assert schema["x-cardinality"] == "ZeroToOne"


# ---------------------------------------------------------------------------
# _coerce_value
# ---------------------------------------------------------------------------


class TestCoerceValue:
    def test_integer_coercion(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value("42", "integer") == 42

    def test_integer_invalid_returns_string(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value("notanumber", "integer") == "notanumber"

    def test_number_coercion(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value("3.14", "number") == 3.14

    def test_number_invalid_returns_string(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value("abc", "number") == "abc"

    def test_boolean_true_variants(self, converter: DefinitionToSchemaConverter) -> None:
        for val in ("true", "True", "1", "yes", " YES "):
            assert converter._coerce_value(val, "boolean") is True

    def test_boolean_false_variants(self, converter: DefinitionToSchemaConverter) -> None:
        for val in ("false", "False", "0", "no", " NO "):
            assert converter._coerce_value(val, "boolean") is False

    def test_boolean_unrecognized_returns_string(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        assert converter._coerce_value("maybe", "boolean") == "maybe"

    def test_none_returns_none(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value(None, "string") is None

    def test_non_string_passthrough(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value(42, "integer") == 42
        assert converter._coerce_value(3.5, "number") == 3.5

    def test_string_type_no_coercion(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._coerce_value("hello", "string") == "hello"


# ---------------------------------------------------------------------------
# _pick_text
# ---------------------------------------------------------------------------


class TestPickText:
    def test_dict_with_en(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._pick_text({"en": "English", "de": "German"}) == "English"

    def test_dict_without_en_picks_first_sorted_key(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        # sorted by key: "de" < "fr", so "Hallo" is picked first
        assert converter._pick_text({"de": "Hallo", "fr": "Bonjour"}) == "Hallo"

    def test_dict_en_key_returns_even_if_empty(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        # "en" key exists, so its value is returned even if empty
        assert converter._pick_text({"en": "", "de": "Wert"}) == ""

    def test_plain_string(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._pick_text("plain text") == "plain text"

    def test_none_returns_empty(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._pick_text(None) == ""

    def test_non_string_non_dict_returns_empty(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        assert converter._pick_text(42) == ""


# ---------------------------------------------------------------------------
# _is_required / cardinality
# ---------------------------------------------------------------------------


class TestIsRequired:
    def test_one_is_required(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._is_required({"smt": {"cardinality": "One"}}) is True

    def test_one_to_many_is_required(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._is_required({"smt": {"cardinality": "OneToMany"}}) is True

    def test_zero_to_one_is_not_required(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._is_required({"smt": {"cardinality": "ZeroToOne"}}) is False

    def test_zero_to_many_is_not_required(self, converter: DefinitionToSchemaConverter) -> None:
        assert converter._is_required({"smt": {"cardinality": "ZeroToMany"}}) is False

    def test_missing_cardinality_is_not_required(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        assert converter._is_required({"smt": {}}) is False
        assert converter._is_required({}) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_definition(self, converter: DefinitionToSchemaConverter) -> None:
        schema = converter.convert({})
        assert schema["type"] == "object"
        assert schema["title"] == "Submodel"
        assert schema["properties"] == {}
        assert schema["required"] == []

    def test_elements_without_id_short_are_skipped(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        definition = {
            "submodel": {
                "idShort": "Test",
                "elements": [
                    {"modelType": "Property", "valueType": "xs:string", "smt": {}},
                ],
            }
        }
        schema = converter.convert(definition)
        assert schema["properties"] == {}

    def test_missing_model_type_defaults_to_property(
        self, converter: DefinitionToSchemaConverter
    ) -> None:
        node = {"idShort": "Bare", "valueType": "xs:string", "smt": {}}
        schema = converter._node_to_schema(node)
        assert schema["type"] == "string"

    def test_deeply_nested_collection(self, converter: DefinitionToSchemaConverter) -> None:
        """5-level nesting mirrors realistic IDTA template depth."""
        inner = {
            "idShort": "Leaf",
            "modelType": "Property",
            "valueType": "xs:string",
            "smt": {},
        }
        for level in range(4):
            inner = {
                "idShort": f"Level{level}",
                "modelType": "SubmodelElementCollection",
                "children": [inner],
                "smt": {},
            }
        definition = {"submodel": {"idShort": "Deep", "elements": [inner]}}
        schema = converter.convert(definition)
        # Walk down 4 collection levels to the leaf
        cursor = schema
        for level in range(3, -1, -1):
            cursor = cursor["properties"][f"Level{level}"]
            assert cursor["type"] == "object"
        assert cursor["properties"]["Leaf"]["type"] == "string"
