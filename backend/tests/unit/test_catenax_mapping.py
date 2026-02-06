# ruff: noqa: ARG002  — pytest fixtures are used via parameter name injection
"""
Unit tests for Catena-X DTR shell descriptor mapping utilities.
"""

from unittest.mock import MagicMock, patch
from urllib.parse import quote
from uuid import uuid4

import pytest

from app.modules.aas.references import extract_semantic_id_str
from app.modules.connectors.catenax.mapping import (
    build_shell_descriptor,
)


def _make_dpp(
    dpp_id=None,
    asset_ids=None,
):
    """Create a mock DPP with the given fields."""
    dpp = MagicMock()
    dpp.id = dpp_id or uuid4()
    dpp.asset_ids = asset_ids or {}
    return dpp


def _make_revision(submodels=None):
    """Create a mock DPPRevision with a given submodel list."""
    revision = MagicMock()
    revision.aas_env_json = {"submodels": submodels or []}
    return revision


def _make_submodel(
    sm_id="urn:sm:1",
    id_short="Nameplate",
    semantic_id_value="urn:samm:io.catenax.serial_part:3.0.0#SerialPart",
):
    """Build a submodel dict matching the AAS JSON structure."""
    return {
        "id": sm_id,
        "idShort": id_short,
        "semanticId": {
            "keys": [{"value": semantic_id_value}],
        },
    }


MOCK_SETTINGS_PATH = "app.modules.connectors.catenax.mapping.get_settings"


@pytest.fixture
def mock_settings():
    """Patch get_settings in the mapping module."""
    with patch(MOCK_SETTINGS_PATH) as mock_get:
        settings = MagicMock()
        settings.keycloak_client_id = "dpp-backend"
        mock_get.return_value = settings
        yield settings


# ---------------------------------------------------------------------------
# build_shell_descriptor
# ---------------------------------------------------------------------------


class TestBuildShellDescriptor:
    def test_shell_descriptor_id_format(self, mock_settings):
        """Descriptor id is 'urn:uuid:{dpp.id}'."""
        dpp_id = uuid4()
        dpp = _make_dpp(dpp_id=dpp_id, asset_ids={"manufacturerPartId": "MP-1"})
        revision = _make_revision(submodels=[])

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        assert desc.id == f"urn:uuid:{dpp_id}"

    def test_global_asset_id_from_asset_ids(self, mock_settings):
        """globalAssetId is taken from dpp.asset_ids when present."""
        dpp = _make_dpp(
            asset_ids={
                "globalAssetId": "urn:global:asset:42",
                "manufacturerPartId": "MP-1",
            }
        )
        revision = _make_revision()

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        assert desc.global_asset_id == "urn:global:asset:42"

    def test_global_asset_id_fallback(self, mock_settings):
        """When globalAssetId is absent, falls back to 'urn:uuid:{dpp.id}'."""
        dpp = _make_dpp(asset_ids={"manufacturerPartId": "MP-1"})
        revision = _make_revision()

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        assert desc.global_asset_id == f"urn:uuid:{dpp.id}"

    def test_specific_asset_ids_excludes_global(self, mock_settings):
        """globalAssetId is not duplicated in the specificAssetIds list."""
        dpp = _make_dpp(
            asset_ids={
                "globalAssetId": "urn:global:1",
                "manufacturerPartId": "MP-1",
                "serialNumber": "SN-001",
            }
        )
        revision = _make_revision()

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        names = [item["name"] for item in desc.specific_asset_ids]
        assert "globalAssetId" not in names
        assert "manufacturerPartId" in names
        assert "serialNumber" in names

    def test_submodel_endpoint_url_encoding(self, mock_settings):
        """Submodel ID is URL-encoded in the endpoint href."""
        sm_id = "urn:sm:special/chars?here"
        dpp = _make_dpp(asset_ids={"manufacturerPartId": "MP-1"})
        revision = _make_revision(submodels=[_make_submodel(sm_id=sm_id)])

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        expected_encoded = quote(sm_id, safe="")
        href = desc.submodel_descriptors[0]["endpoints"][0]["protocolInformation"]["href"]
        assert expected_encoded in href
        assert href == f"https://api.example.com/submodels/{expected_encoded}/$value"

    def test_edc_dsp_fields_present(self, mock_settings):
        """When edc_dsp_endpoint is provided, DSP subprotocol fields are set."""
        dpp = _make_dpp(asset_ids={"manufacturerPartId": "MP-1"})
        revision = _make_revision(submodels=[_make_submodel()])

        desc = build_shell_descriptor(
            dpp,
            revision,
            "https://api.example.com",
            edc_dsp_endpoint="https://edc.example.com/dsp",
        )

        proto_info = desc.submodel_descriptors[0]["endpoints"][0]["protocolInformation"]
        assert proto_info["subprotocol"] == "DSP"
        assert "dspEndpoint=https://edc.example.com/dsp" in proto_info["subprotocolBody"]
        assert proto_info["subprotocolBodyEncoding"] == "plain"

    def test_edc_dsp_fields_absent(self, mock_settings):
        """When edc_dsp_endpoint is None, no subprotocol fields are present."""
        dpp = _make_dpp(asset_ids={"manufacturerPartId": "MP-1"})
        revision = _make_revision(submodels=[_make_submodel()])

        desc = build_shell_descriptor(dpp, revision, "https://api.example.com")

        proto_info = desc.submodel_descriptors[0]["endpoints"][0]["protocolInformation"]
        assert "subprotocol" not in proto_info
        assert "subprotocolBody" not in proto_info
        assert "subprotocolBodyEncoding" not in proto_info


# ---------------------------------------------------------------------------
# _extract_semantic_id
# ---------------------------------------------------------------------------


class TestExtractSemanticId:
    def test_extract_semantic_id_standard(self):
        """Extracts the first key value from a standard semanticId structure."""
        submodel = {
            "semanticId": {
                "keys": [{"value": "urn:samm:io.catenax.pcf:6.0.0#Pcf"}],
            }
        }
        assert extract_semantic_id_str(submodel) == "urn:samm:io.catenax.pcf:6.0.0#Pcf"

    def test_extract_semantic_id_missing_keys(self):
        """Returns empty string when keys list is empty."""
        submodel = {"semanticId": {"keys": []}}
        assert extract_semantic_id_str(submodel) == ""

    def test_extract_semantic_id_missing_semantic_id(self):
        """Returns empty string when semanticId key is absent."""
        submodel = {"idShort": "Nameplate"}
        assert extract_semantic_id_str(submodel) == ""
