"""AAS metamodel conformance tests using aas-test-engines.

These tests validate that the AAS structures produced by the platform
pass the official IDTA/BaSyx conformance checker.  They are gated by
``@pytest.mark.conformance`` so they can be excluded from fast local
runs when the dependency is not installed.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

import pytest

try:
    from aas_test_engines import file as aas_file

    HAS_ENGINES = True
except ImportError:
    HAS_ENGINES = False

skip_no_engines = pytest.mark.skipif(not HAS_ENGINES, reason="aas-test-engines not installed")


def _conformant_aas_env() -> dict[str, Any]:
    """Return an AAS env dict that satisfies the aas-test-engines checker.

    The checker is stricter than BaSyx regarding modelType presence and
    empty arrays, so every identifiable/referable carries modelType and
    lists always have at least one element.
    """
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:aas:conf:1",
                "idShort": "ConfAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:conf:1",
                },
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:conf:1",
                "idShort": "ConfSM",
                "submodelElements": [
                    {
                        "modelType": "Property",
                        "idShort": "Prop1",
                        "valueType": "xs:string",
                        "value": "42",
                    }
                ],
            }
        ],
    }


@pytest.mark.conformance()
class TestAASJsonConformance:
    """Validate AAS JSON output against aas-test-engines metamodel checker."""

    @skip_no_engines
    def test_json_env_passes_metamodel_check(self) -> None:
        """A minimal AAS env should pass the JSON metamodel check."""
        env = _conformant_aas_env()
        result = aas_file.check_json_data(env)  # type: ignore[possibly-undefined]
        assert result.ok(), f"Conformance failures: {result}"

    @skip_no_engines
    def test_json_with_multilang_property(self) -> None:
        """An env with MultiLanguageProperty should still pass."""
        env = _conformant_aas_env()
        env["submodels"][0]["submodelElements"].append(
            {
                "modelType": "MultiLanguageProperty",
                "idShort": "Description",
                "value": [{"language": "en", "text": "A test description"}],
            }
        )
        result = aas_file.check_json_data(env)  # type: ignore[possibly-undefined]
        assert result.ok(), f"Conformance failures: {result}"

    @skip_no_engines
    def test_json_with_collection(self) -> None:
        """An env with SubmodelElementCollection should pass."""
        env = _conformant_aas_env()
        env["submodels"][0]["submodelElements"].append(
            {
                "modelType": "SubmodelElementCollection",
                "idShort": "Details",
                "value": [
                    {
                        "modelType": "Property",
                        "idShort": "InnerProp",
                        "valueType": "xs:integer",
                        "value": "7",
                    }
                ],
            }
        )
        result = aas_file.check_json_data(env)  # type: ignore[possibly-undefined]
        assert result.ok(), f"Conformance failures: {result}"


@pytest.mark.conformance()
class TestAASXmlConformance:
    """Validate AAS XML round-trip against aas-test-engines."""

    @skip_no_engines
    def test_xml_roundtrip_passes_check(self) -> None:
        """BaSyx XML output should parse and pass the XML checker."""
        from app.modules.aas.serialization import aas_to_xml

        env = _conformant_aas_env()
        xml_bytes = aas_to_xml(env)
        root = ET.fromstring(xml_bytes)  # noqa: S314
        result = aas_file.check_xml_data(root)  # type: ignore[possibly-undefined]
        assert result.ok(), f"Conformance failures: {result}"
