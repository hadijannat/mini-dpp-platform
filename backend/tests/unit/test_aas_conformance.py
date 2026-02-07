"""Tests for AAS conformance validation."""

from app.modules.aas.conformance import AASValidationResult, validate_aas_environment


def _minimal_aas_env() -> dict:
    """Return a minimal valid AAS environment dict (BaSyx 2.0 compatible)."""
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:aas:1",
                "idShort": "TestAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:1",
                },
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:1",
                "idShort": "Nameplate",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://admin-shell.io/zvei/nameplate/2/0/Nameplate",
                        }
                    ],
                },
                "submodelElements": [
                    {
                        "idShort": "ManufacturerName",
                        "modelType": "MultiLanguageProperty",
                        "semanticId": {
                            "type": "ExternalReference",
                            "keys": [
                                {
                                    "type": "GlobalReference",
                                    "value": "0173-1#02-AAO677#002",
                                }
                            ],
                        },
                        "value": [{"language": "en", "text": "ACME Corp"}],
                    }
                ],
            }
        ],
        "conceptDescriptions": [],
    }


class TestAASValidationResult:
    def test_default_is_valid(self) -> None:
        result = AASValidationResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []


class TestValidateAASEnvironment:
    def test_valid_environment(self) -> None:
        env = _minimal_aas_env()
        result = validate_aas_environment(env)
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_submodels_key(self) -> None:
        env = {"assetAdministrationShells": []}
        result = validate_aas_environment(env)
        assert result.is_valid is False
        assert any("submodels" in e for e in result.errors)

    def test_missing_aas_key(self) -> None:
        env = {"submodels": []}
        result = validate_aas_environment(env)
        assert result.is_valid is False
        assert any("assetAdministrationShells" in e for e in result.errors)

    def test_empty_environment(self) -> None:
        env: dict = {}
        result = validate_aas_environment(env)
        assert result.is_valid is False

    def test_aas_missing_id(self) -> None:
        env = {
            "assetAdministrationShells": [
                {
                    "assetInformation": {
                        "assetKind": "Instance",
                        "globalAssetId": "urn:asset:1",
                    },
                }
            ],
            "submodels": [],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False
        assert any("'id'" in e for e in result.errors)

    def test_aas_missing_asset_information(self) -> None:
        env = {
            "assetAdministrationShells": [{"id": "urn:aas:1"}],
            "submodels": [],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False
        assert any("'assetInformation'" in e for e in result.errors)

    def test_submodel_missing_id(self) -> None:
        env = {
            "assetAdministrationShells": [],
            "submodels": [{"idShort": "NoId"}],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False
        assert any("'id'" in e for e in result.errors)

    def test_submodel_missing_semantic_id_warns(self) -> None:
        env = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:nosem",
                    "idShort": "NoSemantic",
                    "submodelElements": [],
                }
            ],
        }
        result = validate_aas_environment(env)
        # Should still be valid but with a warning
        assert result.is_valid is True
        assert any("semanticId" in w for w in result.warnings)

    def test_non_list_aas_shells(self) -> None:
        env = {
            "assetAdministrationShells": "not-a-list",
            "submodels": [],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False

    def test_non_list_submodels(self) -> None:
        env = {
            "assetAdministrationShells": [],
            "submodels": "not-a-list",
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False

    def test_non_dict_shell_entry(self) -> None:
        env = {
            "assetAdministrationShells": ["not-a-dict"],
            "submodels": [],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False

    def test_non_dict_submodel_entry(self) -> None:
        env = {
            "assetAdministrationShells": [],
            "submodels": [42],
        }
        result = validate_aas_environment(env)
        assert result.is_valid is False

    def test_basyx_roundtrip_failure_invalid_json(self) -> None:
        """An env that passes structural checks but fails BaSyx deserialization."""
        env = {
            "assetAdministrationShells": [
                {
                    "id": "urn:aas:bad",
                    "assetInformation": {
                        "assetKind": "INVALID_KIND_VALUE_12345",
                        "globalAssetId": "urn:asset:bad",
                    },
                }
            ],
            "submodels": [],
        }
        result = validate_aas_environment(env)
        # BaSyx should fail on the invalid assetKind with failsafe=False
        assert result.is_valid is False
        assert any("BaSyx" in e for e in result.errors)

    def test_valid_with_properties(self) -> None:
        """Full env with properties gets semantic warnings but is valid."""
        env = _minimal_aas_env()
        # Add a property without semantic ID
        env["submodels"][0]["submodelElements"].append(
            {
                "idShort": "NoSemanticProp",
                "modelType": "Property",
                "valueType": "xs:string",
                "value": "test",
            }
        )
        result = validate_aas_environment(env)
        assert result.is_valid is True
        # Should warn about missing semantic ID on property
        assert any("NoSemanticProp" in w for w in result.warnings)

    def test_contract_b_import(self) -> None:
        """Verify Contract B: the function is importable from the expected path."""
        from app.modules.aas.conformance import (
            AASValidationResult as AVR,
        )
        from app.modules.aas.conformance import (
            validate_aas_environment as vae,
        )

        assert AVR is not None
        assert callable(vae)

    def test_asset_info_missing_global_asset_id_warns(self) -> None:
        env = {
            "assetAdministrationShells": [
                {
                    "id": "urn:aas:1",
                    "assetInformation": {
                        "assetKind": "Instance",
                    },
                }
            ],
            "submodels": [],
        }
        result = validate_aas_environment(env)
        assert any("globalAssetId" in w for w in result.warnings)
