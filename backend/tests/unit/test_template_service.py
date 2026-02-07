"""Unit tests for deterministic template registry behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.templates.catalog import (
    TEMPLATE_CATALOG,
    get_template_descriptor,
    list_template_keys,
)
from app.modules.templates.service import TemplateRegistryService


class TestTemplateRegistryService:
    def test_template_catalog_contains_only_dpp40_core_templates(self):
        expected = [
            "carbon-footprint",
            "contact-information",
            "digital-nameplate",
            "handover-documentation",
            "hierarchical-structures",
            "technical-data",
        ]
        assert list_template_keys() == expected
        for template_key in expected:
            descriptor = TEMPLATE_CATALOG[template_key]
            assert descriptor.semantic_id.startswith("https://")
            assert descriptor.repo_folder
            assert descriptor.baseline_major >= 1

    def test_generate_ui_schema_is_derived_from_definition_ast(self):
        mock_session = MagicMock()
        service = TemplateRegistryService(mock_session)

        definition = {
            "submodel": {
                "idShort": "Nameplate",
                "elements": [
                    {
                        "idShort": "ManufacturerName",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "description": {"en": "Name of manufacturer"},
                        "smt": {"cardinality": "One"},
                    },
                    {
                        "idShort": "Threshold",
                        "modelType": "Property",
                        "valueType": "xs:integer",
                        "smt": {
                            "allowed_range": {"min": 0, "max": 100, "raw": "0..100"},
                        },
                    },
                ],
            }
        }

        mock_template = MagicMock()
        service.generate_template_definition = MagicMock(return_value=definition)

        schema = service.generate_ui_schema(mock_template)

        assert schema["type"] == "object"
        assert schema["required"] == ["ManufacturerName"]
        assert schema["properties"]["Threshold"]["minimum"] == 0
        assert schema["properties"]["Threshold"]["maximum"] == 100

    def test_select_template_file_prefers_expected_exact_name(self):
        service = TemplateRegistryService(MagicMock())

        files = [
            {
                "name": "Sample_TechnicalData.json",
                "download_url": "https://example.test/sample.json",
            },
            {
                "name": "IDTA_02003_2-0-1_Template_TechnicalData.json",
                "download_url": "https://example.test/template.json",
            },
        ]

        selected = service._select_template_file(
            files,
            prefer_kind="json",
            expected_name="IDTA_02003_2-0-1_Template_TechnicalData.json",
        )

        assert selected is not None
        assert selected["download_url"] == "https://example.test/template.json"

    def test_select_template_file_uses_deterministic_ranking(self):
        service = TemplateRegistryService(MagicMock())

        files = [
            {
                "name": "TechnicalData_sample.json",
                "download_url": "https://example.test/sample.json",
            },
            {
                "name": "TechnicalData_schema.json",
                "download_url": "https://example.test/schema.json",
            },
            {
                "name": "TechnicalData_template.json",
                "download_url": "https://example.test/template.json",
            },
        ]

        selected = service._select_template_file(files, prefer_kind="json")
        assert selected is not None
        assert selected["download_url"] == "https://example.test/template.json"

    @pytest.mark.asyncio
    async def test_resolve_template_version_uses_latest_patch_within_baseline(self):
        service = TemplateRegistryService(MagicMock())
        descriptor = get_template_descriptor("technical-data")
        assert descriptor is not None

        service._settings.template_version_resolution_policy = "latest_patch"
        service._settings.template_major_minor_baselines["technical-data"] = "2.0"
        service._list_available_patches = AsyncMock(return_value=[0, 3, 1])
        resolved = await service._resolve_template_version(descriptor)

        assert resolved == "2.0.3"

    def test_version_key_is_semantic(self):
        service = TemplateRegistryService(MagicMock())
        versions = ["1.0.9", "1.0.11", "1.0.2"]

        sorted_versions = sorted(versions, key=service._version_key, reverse=True)
        assert sorted_versions == ["1.0.11", "1.0.9", "1.0.2"]
