"""
Unit tests for Template Registry Service.
"""

from unittest.mock import MagicMock

from app.modules.templates.catalog import TEMPLATE_CATALOG
from app.modules.templates.service import TemplateRegistryService


class TestTemplateRegistryService:
    """Tests for template fetching, parsing, and schema generation."""

    def test_template_catalog_contains_expected(self):
        """Test that all DPP4.0 templates have catalog entries defined."""
        expected_templates = [
            "digital-nameplate",
            "contact-information",
            "technical-data",
            "carbon-footprint",
            "handover-documentation",
            "hierarchical-structures",
        ]

        for template_key in expected_templates:
            assert template_key in TEMPLATE_CATALOG
            descriptor = TEMPLATE_CATALOG[template_key]
            assert descriptor.semantic_id.startswith("https://")
            assert descriptor.repo_folder

    def test_generate_ui_schema_from_property(self):
        """Test UI schema generation for simple Property elements."""
        # Create a mock session
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        # Mock template with a simple property
        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "ManufacturerName",
                            "modelType": {"name": "Property"},
                            "valueType": "xs:string",
                            "description": [{"language": "en", "text": "Name of manufacturer"}],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)

        assert schema["type"] == "object"
        assert "ManufacturerName" in schema["properties"]
        assert schema["properties"]["ManufacturerName"]["type"] == "string"
        assert schema["properties"]["ManufacturerName"]["title"] == "ManufacturerName"

    def test_generate_ui_schema_nested_collection(self):
        """Test UI schema generation for nested SubmodelElementCollections."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "Nameplate",
                    "submodelElements": [
                        {
                            "idShort": "ContactInfo",
                            "modelType": {"name": "SubmodelElementCollection"},
                            "value": [
                                {
                                    "idShort": "Email",
                                    "modelType": {"name": "Property"},
                                    "valueType": "xs:string",
                                },
                                {
                                    "idShort": "Phone",
                                    "modelType": {"name": "Property"},
                                    "valueType": "xs:string",
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)

        assert "ContactInfo" in schema["properties"]
        assert schema["properties"]["ContactInfo"]["type"] == "object"
        assert "Email" in schema["properties"]["ContactInfo"]["properties"]
        assert "Phone" in schema["properties"]["ContactInfo"]["properties"]

    def test_generate_ui_schema_multi_language_property(self):
        """Test UI schema generation for MultiLanguageProperty."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "ProductDescription",
                            "modelType": {"name": "MultiLanguageProperty"},
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)

        assert "ProductDescription" in schema["properties"]
        assert schema["properties"]["ProductDescription"]["x-multi-language"] is True

    def test_generate_ui_schema_range(self):
        """Test UI schema generation for Range elements."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "TemperatureRange",
                            "modelType": {"name": "Range"},
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)

        assert "TemperatureRange" in schema["properties"]
        assert schema["properties"]["TemperatureRange"]["x-range"] is True
        assert "min" in schema["properties"]["TemperatureRange"]["properties"]
        assert "max" in schema["properties"]["TemperatureRange"]["properties"]

    def test_generate_ui_schema_file(self):
        """Test UI schema generation for File elements."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "ProductImage",
                            "modelType": {"name": "File"},
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)

        assert "ProductImage" in schema["properties"]
        assert schema["properties"]["ProductImage"]["x-file-upload"] is True

    def test_generate_ui_schema_cardinality_required(self):
        """Cardinality qualifiers should mark required fields."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "RequiredField",
                            "modelType": {"name": "Property"},
                            "valueType": "xs:string",
                            "qualifiers": [{"type": "Cardinality", "value": "One"}],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        assert "RequiredField" in schema["required"]

    def test_generate_ui_schema_default_and_range(self):
        """Default values and allowed ranges should map to JSON Schema."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "Threshold",
                            "modelType": {"name": "Property"},
                            "valueType": "xs:integer",
                            "qualifiers": [
                                {"type": "SMT/DefaultValue", "value": "10"},
                                {"type": "SMT/AllowedRange", "value": "0..100"},
                                {"type": "SMT/AccessMode", "value": "ReadOnly"},
                                {"type": "SMT/FormTitle", "value": "Threshold Value"},
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        field = schema["properties"]["Threshold"]
        assert field["default"] == 10
        assert field["minimum"] == 0
        assert field["maximum"] == 100
        assert field["readOnly"] is True
        assert field["title"] == "Threshold Value"

    def test_generate_ui_schema_allowed_value_regex(self):
        """AllowedValue qualifiers should map to regex patterns."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "PatternField",
                            "modelType": {"name": "Property"},
                            "valueType": "xs:string",
                            "qualifiers": [
                                {"type": "SMT/AllowedValue", "value": "^[A-Z]{3}$"},
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        field = schema["properties"]["PatternField"]
        assert field["pattern"] == "^[A-Z]{3}$"
        assert field["x-allowed-value"] == "^[A-Z]{3}$"

    def test_generate_ui_schema_form_choices_enum(self):
        """FormChoices should map to enum choices for string fields."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "Mode",
                            "modelType": {"name": "Property"},
                            "valueType": "xs:string",
                            "qualifiers": [
                                {"type": "SMT/FormChoices", "value": "A;B;C"},
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        field = schema["properties"]["Mode"]
        assert field["enum"] == ["A", "B", "C"]
        assert field["x-form-choices"] == ["A", "B", "C"]

    def test_generate_ui_schema_id_short_controls(self):
        """AllowedIdShort/EditIdShort/Naming should be surfaced in schema hints."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "DynamicGroup",
                            "modelType": {"name": "SubmodelElementCollection"},
                            "value": [],
                            "qualifiers": [
                                {"type": "SMT/AllowedIdShort", "value": "SlotA,SlotB"},
                                {"type": "SMT/EditIdShort", "value": "true"},
                                {"type": "SMT/Naming", "value": "Counter"},
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        field = schema["properties"]["DynamicGroup"]
        assert field["x-allowed-id-short"] == ["SlotA", "SlotB"]
        assert field["x-edit-id-short"] is True
        assert field["x-naming"] == "Counter"

    def test_generate_ui_schema_list_cardinality(self):
        """OneToMany list cardinality should set minItems=1."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        mock_template = MagicMock()
        mock_template.template_json = {
            "submodels": [
                {
                    "idShort": "TestSubmodel",
                    "submodelElements": [
                        {
                            "idShort": "Items",
                            "modelType": {"name": "SubmodelElementList"},
                            "qualifiers": [{"type": "SMT/Cardinality", "value": "OneToMany"}],
                            "value": [
                                {
                                    "idShort": "Item",
                                    "modelType": {"name": "Property"},
                                    "valueType": "xs:string",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        schema = service.generate_ui_schema(mock_template)
        field = schema["properties"]["Items"]
        assert field["type"] == "array"
        assert field["minItems"] == 1
