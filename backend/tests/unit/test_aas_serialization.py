"""Tests for AAS serialization (JSON-LD and XML)."""

from xml.etree import ElementTree as ET

from app.modules.aas.serialization import aas_to_jsonld, aas_to_xml


def _minimal_aas_env() -> dict:
    """Return a minimal valid AAS environment for serialization tests."""
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
                    },
                    {
                        "idShort": "SerialNumber",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "value": "SN-12345",
                        "semanticId": {
                            "type": "ExternalReference",
                            "keys": [
                                {
                                    "type": "GlobalReference",
                                    "value": "0173-1#02-AAM556#002",
                                }
                            ],
                        },
                    },
                ],
            }
        ],
        "conceptDescriptions": [
            {
                "modelType": "ConceptDescription",
                "id": "0173-1#02-AAO677#002",
                "idShort": "ManufacturerName",
            }
        ],
    }


class TestAASToJsonLD:
    def test_has_context(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        assert "@context" in result
        ctx = result["@context"]
        assert "aas" in ctx
        assert "td" in ctx

    def test_has_type(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        assert result["@type"] == "aas:Environment"

    def test_has_graph(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        assert "@graph" in result
        assert isinstance(result["@graph"], list)

    def test_aas_shell_in_graph(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        shells = [n for n in result["@graph"] if "AssetAdministrationShell" in n.get("@type", "")]
        assert len(shells) == 1
        assert shells[0]["@id"] == "urn:aas:1"
        assert shells[0]["aas:idShort"] == "TestAAS"

    def test_submodel_in_graph(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        submodels = [n for n in result["@graph"] if "Submodel" in n.get("@type", "")]
        assert len(submodels) == 1
        assert submodels[0]["@id"] == "urn:sm:1"
        assert submodels[0]["aas:idShort"] == "Nameplate"

    def test_submodel_has_semantic_id(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        submodels = [n for n in result["@graph"] if "Submodel" in n.get("@type", "")]
        assert submodels[0]["aas:semanticId"] == (
            "https://admin-shell.io/zvei/nameplate/2/0/Nameplate"
        )

    def test_submodel_elements_included(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        submodels = [n for n in result["@graph"] if "Submodel" in n.get("@type", "")]
        elements = submodels[0].get("aas:submodelElements", [])
        assert len(elements) == 2

    def test_concept_description_in_graph(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        cds = [n for n in result["@graph"] if "ConceptDescription" in n.get("@type", "")]
        assert len(cds) == 1
        assert cds[0]["@id"] == "0173-1#02-AAO677#002"

    def test_aas_asset_information(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        shells = [n for n in result["@graph"] if "AssetAdministrationShell" in n.get("@type", "")]
        ai = shells[0].get("aas:assetInformation")
        assert ai is not None
        assert ai["aas:assetKind"] == "Instance"
        assert ai["aas:globalAssetId"] == "urn:asset:1"

    def test_empty_environment(self) -> None:
        env: dict = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        result = aas_to_jsonld(env)
        assert result["@graph"] == []

    def test_property_value_in_element(self) -> None:
        result = aas_to_jsonld(_minimal_aas_env())
        submodels = [n for n in result["@graph"] if "Submodel" in n.get("@type", "")]
        elements = submodels[0].get("aas:submodelElements", [])
        prop = [e for e in elements if e.get("aas:idShort") == "SerialNumber"]
        assert len(prop) == 1
        assert prop[0]["aas:value"] == "SN-12345"


class TestAASToXML:
    def test_produces_valid_xml(self) -> None:
        xml_bytes = aas_to_xml(_minimal_aas_env())
        assert xml_bytes
        # Should be parseable XML
        root = ET.fromstring(xml_bytes)
        assert root is not None

    def test_xml_contains_aas_namespace(self) -> None:
        xml_bytes = aas_to_xml(_minimal_aas_env())
        xml_str = xml_bytes.decode("utf-8")
        assert "admin-shell.io" in xml_str or "aas" in xml_str.lower()

    def test_xml_contains_submodel(self) -> None:
        xml_bytes = aas_to_xml(_minimal_aas_env())
        xml_str = xml_bytes.decode("utf-8")
        # BaSyx XML serializer includes submodel elements
        assert "urn:sm:1" in xml_str

    def test_xml_contains_aas_shell(self) -> None:
        xml_bytes = aas_to_xml(_minimal_aas_env())
        xml_str = xml_bytes.decode("utf-8")
        assert "urn:aas:1" in xml_str

    def test_empty_env_produces_xml(self) -> None:
        env = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        xml_bytes = aas_to_xml(env)
        root = ET.fromstring(xml_bytes)
        assert root is not None
