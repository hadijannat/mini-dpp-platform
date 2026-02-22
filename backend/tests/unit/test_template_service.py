"""Unit tests for deterministic template registry behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from basyx.aas import model

from app.modules.templates.catalog import (
    TEMPLATE_CATALOG,
    get_template_descriptor,
    list_template_keys,
)
from app.modules.templates.service import (
    TemplateCandidateResolution,
    TemplateRegistryService,
)


class TestTemplateRegistryService:
    def test_template_catalog_contains_only_dpp40_core_templates(self):
        expected = [
            "battery-passport",
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
            assert descriptor.semantic_id  # URL or ECLASS IRI
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
        service._generate_template_definition = MagicMock(return_value=definition)

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

    def test_select_ranked_candidate_prefers_expected_filename(self):
        service = TemplateRegistryService(MagicMock())
        descriptor = get_template_descriptor("technical-data")
        assert descriptor is not None

        selected = service._select_ranked_candidate_resolution(
            [
                TemplateCandidateResolution(
                    asset={
                        "name": "IDTA 02003_2-0-1_Template_TechnicalData_forAASMetamodelV3.1.json"
                    },
                    kind="json",
                    aas_env_json={"submodels": []},
                    aas_env_json_raw={"submodels": []},
                    aasx_bytes=None,
                    source_url="https://example.test/for-metamodel.json",
                    selected_submodel_semantic_id="0173-1#01-AHX837#002",
                    selection_strategy="semantic",
                ),
                TemplateCandidateResolution(
                    asset={"name": "IDTA 02003_2-0-1_Template_TechnicalData.json"},
                    kind="json",
                    aas_env_json={"submodels": []},
                    aas_env_json_raw={"submodels": []},
                    aasx_bytes=None,
                    source_url="https://example.test/template.json",
                    selected_submodel_semantic_id="0173-1#01-AHX837#002",
                    selection_strategy="semantic",
                ),
            ],
            descriptor=descriptor,
            version="2.0.1",
            file_kind="json",
        )

        assert selected is not None
        assert selected.source_url == "https://example.test/template.json"

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

    @pytest.mark.asyncio
    async def test_generate_template_contract_returns_complete_payload(self):
        service = TemplateRegistryService(MagicMock())

        definition = {
            "submodel": {
                "idShort": "TechnicalData",
                "elements": [
                    {
                        "idShort": "MaxTemp",
                        "modelType": "Property",
                        "valueType": "xs:double",
                        "smt": {"cardinality": "One"},
                    },
                ],
            }
        }

        mock_template = MagicMock()
        mock_template.template_key = "technical-data"
        mock_template.idta_version = "2.0.1"
        mock_template.semantic_id = "https://admin-shell.io/ZVEI/TechnicalData/Submodel/1/2"
        mock_template.resolved_version = "2.0.1"
        mock_template.source_repo_ref = "main"
        mock_template.source_file_path = "TechnicalData/2/0/1/template.json"
        mock_template.source_file_sha = "abc123"
        mock_template.source_kind = "json"
        mock_template.selection_strategy = "deterministic_v2"
        mock_template.source_url = "https://raw.githubusercontent.com/example/template.json"

        service._generate_template_definition = MagicMock(return_value=definition)
        service._load_uom_registry_indexes = AsyncMock(return_value=({}, {}, {}))

        contract = await service.generate_template_contract(mock_template)

        # All top-level keys present
        assert contract["template_key"] == "technical-data"
        assert contract["idta_version"] == "2.0.1"
        assert contract["semantic_id"].startswith("https://")

        # Definition is the raw definition AST
        assert contract["definition"]["submodel"]["idShort"] == "TechnicalData"

        # Schema is derived from definition
        schema = contract["schema"]
        assert schema["type"] == "object"
        assert "MaxTemp" in schema["properties"]
        assert schema["required"] == ["MaxTemp"]

        # Source metadata is populated with all expected fields
        meta = contract["source_metadata"]
        assert meta["resolved_version"] == "2.0.1"
        assert meta["source_repo_ref"] == "main"
        assert meta["source_file_path"] == "TechnicalData/2/0/1/template.json"
        assert meta["source_file_sha"] == "abc123"
        assert meta["source_kind"] == "json"
        assert meta["selection_strategy"] == "deterministic_v2"
        assert "source_url" in meta
        assert "dropin_resolution_report" in contract
        assert isinstance(contract["dropin_resolution_report"], list)
        assert "unsupported_nodes" in contract
        assert isinstance(contract["unsupported_nodes"], list)
        assert "uom_diagnostics" in contract
        assert "summary" in contract["uom_diagnostics"]
        assert "issues" in contract["uom_diagnostics"]

    @pytest.mark.asyncio
    async def test_generate_template_contract_definition_and_schema_are_consistent(self):
        """The schema in the contract must be derivable from the definition in the same contract."""
        from app.modules.templates.schema_from_definition import DefinitionToSchemaConverter

        service = TemplateRegistryService(MagicMock())

        definition = {
            "submodel": {
                "idShort": "Nameplate",
                "elements": [
                    {
                        "idShort": "SerialNumber",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "smt": {},
                    },
                ],
            }
        }

        mock_template = MagicMock()
        mock_template.template_key = "digital-nameplate"
        mock_template.idta_version = "3.0.1"
        mock_template.semantic_id = "https://admin-shell.io/zvei/nameplate/2/0/Nameplate"
        mock_template.resolved_version = "3.0.1"
        mock_template.source_repo_ref = "main"
        mock_template.source_file_path = None
        mock_template.source_file_sha = None
        mock_template.source_kind = None
        mock_template.selection_strategy = None
        mock_template.source_url = ""

        service._generate_template_definition = MagicMock(return_value=definition)
        service._load_uom_registry_indexes = AsyncMock(return_value=({}, {}, {}))

        contract = await service.generate_template_contract(mock_template)

        # Re-derive schema from the definition in the contract
        re_derived = DefinitionToSchemaConverter().convert(contract["definition"])
        assert contract["schema"] == re_derived

    @pytest.mark.asyncio
    async def test_generate_template_contract_enriches_unit_resolution(self):
        service = TemplateRegistryService(MagicMock())
        definition = {
            "submodel": {"idShort": "TechnicalData", "elements": []},
            "concept_descriptions": [
                {
                    "id": "urn:cd:length",
                    "dataType": "REAL_MEASURE",
                    "unit": "m",
                    "unitId": "urn:unit:m",
                }
            ],
        }

        mock_template = MagicMock()
        mock_template.template_key = "technical-data"
        mock_template.idta_version = "2.0.1"
        mock_template.semantic_id = "https://example.org/technical-data"
        mock_template.resolved_version = "2.0.1"
        mock_template.source_repo_ref = "main"
        mock_template.source_file_path = None
        mock_template.source_file_sha = None
        mock_template.source_kind = "json"
        mock_template.selection_strategy = "deterministic_v2"
        mock_template.source_url = "https://example.org/template.json"
        mock_template.template_json = {"conceptDescriptions": []}
        mock_template.template_json_raw = {
            "conceptDescriptions": [
                {
                    "id": "urn:unit:m",
                    "embeddedDataSpecifications": [
                        {
                            "dataSpecification": {
                                "keys": [
                                    {
                                        "value": (
                                            "https://admin-shell.io/DataSpecificationTemplates/"
                                            "DataSpecificationUoM/3"
                                        )
                                    }
                                ]
                            },
                            "dataSpecificationContent": {
                                "modelType": "DataSpecificationUoM",
                                "preferredName": [{"language": "en", "text": "metre"}],
                                "symbol": "m",
                                "specificUnitID": "MTR",
                                "classificationSystem": "UNECE Rec 20",
                            },
                        }
                    ],
                }
            ]
        }

        service._generate_template_definition = MagicMock(return_value=definition)
        service._load_uom_registry_indexes = AsyncMock(return_value=({}, {}, {}))

        contract = await service.generate_template_contract(mock_template)

        concept_description = contract["definition"]["concept_descriptions"][0]
        assert concept_description["unitResolutionStatus"] == "resolved"
        assert concept_description["unitResolved"]["symbol"] == "m"
        assert contract["uom_diagnostics"]["summary"]["unit_links_resolved"] == 1

    def test_unknown_model_types_are_opt_in_for_unsupported_nodes(self):
        service = TemplateRegistryService(MagicMock())
        definition = {
            "submodel": {
                "idShort": "TechnicalData",
                "elements": [
                    {
                        "path": "TechnicalData.GenericItems",
                        "idShort": "GenericItems",
                        "modelType": "SubmodelElement",
                    }
                ],
            }
        }
        schema = {
            "type": "object",
            "properties": {
                "GenericItems": {
                    "type": "object",
                    "x-readonly": True,
                }
            },
        }

        default_unsupported = service._collect_unsupported_nodes(
            definition=definition,
            schema=schema,
        )
        strict_unsupported = service._collect_unsupported_nodes(
            definition=definition,
            schema=schema,
            strict_unknown_model_types=True,
        )

        assert default_unsupported == []
        assert strict_unsupported
        assert strict_unsupported[0]["modelType"] == "SubmodelElement"
        assert "unsupported_model_type:SubmodelElement" in strict_unsupported[0]["reasons"]

    def test_generate_template_definition_expands_dropins_from_template_lookup(self):
        service = TemplateRegistryService(MagicMock())

        target_semantic = (
            "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/AddressInformation"
        )
        source_semantic = (
            "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/ContactInformation"
        )

        def _ref(iri: str) -> model.Reference:
            return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, iri),))

        target_submodel = model.Submodel(
            id_="urn:test:nameplate",
            id_short="Nameplate",
            submodel_element=[
                model.SubmodelElementCollection(
                    id_short="AddressInformation",
                    semantic_id=_ref(target_semantic),
                    value=[],
                )
            ],
        )
        source_submodel = model.Submodel(
            id_="urn:test:contact",
            id_short="ContactInformations",
            submodel_element=[
                model.SubmodelElementCollection(
                    id_short="ContactInformation",
                    semantic_id=_ref(source_semantic),
                    value=[
                        model.Property(
                            id_short="Street",
                            value_type=model.datatypes.String,
                            value=None,
                        )
                    ],
                )
            ],
        )

        target_template = MagicMock()
        target_template.template_key = "digital-nameplate"
        target_template.idta_version = "3.0.1"
        target_template.source_file_sha = "sha-target"
        target_template.semantic_id = target_semantic
        target_template.template_aasx = None
        target_template.template_json = {}

        source_template = MagicMock()
        source_template.template_key = "contact-information"
        source_template.idta_version = "1.0.1"
        source_template.source_file_sha = "sha-source"
        source_template.semantic_id = source_semantic
        source_template.template_aasx = None
        source_template.template_json = {}

        service._parse_template_model = MagicMock(
            side_effect=[
                MagicMock(submodel=target_submodel, concept_descriptions=[]),
                MagicMock(submodel=source_submodel, concept_descriptions=[]),
            ]
        )

        definition = service.generate_template_definition(
            target_template,
            template_lookup={
                "digital-nameplate": target_template,
                "contact-information": source_template,
            },
        )

        address_node = definition["submodel"]["elements"][0]
        assert address_node["idShort"] == "AddressInformation"
        assert len(address_node.get("children") or []) == 1
        assert address_node.get("x_resolution", {}).get("status") == "resolved"

    @pytest.mark.asyncio
    async def test_refresh_all_templates_reports_skipped_unavailable_templates(self):
        session = AsyncMock()
        service = TemplateRegistryService(session)

        async def _fake_refresh(template_key: str):
            template = MagicMock()
            template.template_key = template_key
            template.idta_version = "1.0.1"
            template.resolved_version = "1.0.1"
            template.semantic_id = "urn:test:semantic"
            template.source_url = "https://example.test/template.json"
            template.source_repo_ref = "main"
            template.source_file_path = f"published/{template_key}/template.json"
            template.source_file_sha = "sha123"
            template.source_kind = "json"
            template.selection_strategy = "deterministic_v2"
            template.fetched_at = datetime.now(UTC)
            return template

        service.refresh_template = AsyncMock(side_effect=_fake_refresh)  # type: ignore[method-assign]

        templates, results = await service.refresh_all_templates()

        skipped = [r for r in results if r.template_key == "battery-passport"]
        assert skipped and skipped[0].status == "skipped"
        assert skipped[0].support_status == "unavailable"
        assert "unavailable" in (skipped[0].error or "")

        refreshed_keys = {t.template_key for t in templates}
        assert "battery-passport" not in refreshed_keys
        assert session.commit.await_count == 1
