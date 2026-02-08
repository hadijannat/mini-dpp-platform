"""Tests for AASRepositoryService — submodel extraction and listing."""

from __future__ import annotations

from app.modules.dpps.repository import AASRepositoryService


def _sample_aas_env() -> dict:
    """Return a sample AAS environment with two submodels."""
    return {
        "assetAdministrationShells": [{"id": "urn:uuid:aas-1", "idShort": "TestAAS"}],
        "submodels": [
            {
                "id": "urn:example:nameplate",
                "idShort": "DigitalNameplate",
                "submodelElements": [{"idShort": "ManufacturerName", "value": "Acme"}],
            },
            {
                "id": "urn:example:carbon",
                "idShort": "CarbonFootprint",
                "submodelElements": [{"idShort": "TotalCO2", "value": "42"}],
            },
        ],
    }


class TestGetSubmodelFromRevision:
    """Test static submodel extraction from AAS environments."""

    def test_returns_matching_submodel(self) -> None:
        env = _sample_aas_env()
        result = AASRepositoryService.get_submodel_from_revision(env, "urn:example:nameplate")
        assert result is not None
        assert result["idShort"] == "DigitalNameplate"

    def test_returns_none_for_unknown_id(self) -> None:
        env = _sample_aas_env()
        result = AASRepositoryService.get_submodel_from_revision(env, "urn:example:missing")
        assert result is None

    def test_returns_none_for_empty_env(self) -> None:
        result = AASRepositoryService.get_submodel_from_revision({}, "urn:x")
        assert result is None


class TestListSubmodelIds:
    """Test submodel ID listing."""

    def test_lists_all_submodel_ids(self) -> None:
        env = _sample_aas_env()
        ids = AASRepositoryService.list_submodel_ids(env)
        assert ids == ["urn:example:nameplate", "urn:example:carbon"]

    def test_empty_env_returns_empty_list(self) -> None:
        ids = AASRepositoryService.list_submodel_ids({})
        assert ids == []

    def test_env_with_no_submodels_key(self) -> None:
        ids = AASRepositoryService.list_submodel_ids({"assetAdministrationShells": []})
        assert ids == []
