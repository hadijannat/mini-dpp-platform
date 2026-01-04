"""
Unit tests for Template Registry Service.
"""

from unittest.mock import MagicMock

from app.modules.templates.service import TEMPLATE_SEMANTIC_IDS, TemplateRegistryService


class TestTemplateRegistryService:
    """Tests for template fetching, parsing, and schema generation."""

    def test_template_semantic_ids_defined(self):
        """Test that all DPP4.0 templates have semantic IDs defined."""
        expected_templates = [
            "digital-nameplate",
            "contact-information",
            "technical-data",
            "carbon-footprint",
            "handover-documentation",
            "hierarchical-structures",
        ]

        for template_key in expected_templates:
            assert template_key in TEMPLATE_SEMANTIC_IDS
            assert TEMPLATE_SEMANTIC_IDS[template_key].startswith("https://")

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

    def test_get_default_elements_digital_nameplate(self):
        """Test default elements generation for digital-nameplate template."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        elements = service._get_default_elements("digital-nameplate")

        assert len(elements) > 0
        element_ids = [e["idShort"] for e in elements]
        assert "ManufacturerName" in element_ids
        assert "SerialNumber" in element_ids

    def test_get_default_elements_carbon_footprint(self):
        """Test default elements generation for carbon-footprint template."""
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        elements = service._get_default_elements("carbon-footprint")

        assert len(elements) > 0
        element_ids = [e["idShort"] for e in elements]
        assert "PCFCO2eq" in element_ids
