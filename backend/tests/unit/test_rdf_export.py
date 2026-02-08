"""Tests for RDF/Turtle export functionality."""

from __future__ import annotations

import json
from typing import Any

import rdflib

from app.modules.aas.serialization import aas_to_jsonld, aas_to_turtle


def _sample_aas_env() -> dict[str, Any]:
    """Return a sample AAS environment for RDF tests."""
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:aas:rdf-test:1",
                "idShort": "RDFTestAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:rdf-test:1",
                },
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:rdf-test:1",
                "idShort": "TestSubmodel",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {
                            "type": "GlobalReference",
                            "value": "https://example.org/sm/test",
                        }
                    ],
                },
                "submodelElements": [
                    {
                        "idShort": "Temperature",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "value": "42",
                    },
                ],
            }
        ],
        "conceptDescriptions": [],
    }


class TestAASToTurtle:
    """Tests for the aas_to_turtle() function."""

    def test_returns_string(self) -> None:
        result = aas_to_turtle(_sample_aas_env())
        assert isinstance(result, str)

    def test_produces_valid_turtle(self) -> None:
        """Turtle output should parse back through rdflib without error."""
        turtle_str = aas_to_turtle(_sample_aas_env())
        g = rdflib.Graph()
        g.parse(data=turtle_str, format="turtle")
        assert len(g) > 0

    def test_contains_aas_namespace(self) -> None:
        turtle_str = aas_to_turtle(_sample_aas_env())
        assert "admin-shell.io" in turtle_str

    def test_contains_subject_uris(self) -> None:
        turtle_str = aas_to_turtle(_sample_aas_env())
        assert "urn:aas:rdf-test:1" in turtle_str
        assert "urn:sm:rdf-test:1" in turtle_str

    def test_empty_env_produces_valid_turtle(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [],
        }
        turtle_str = aas_to_turtle(env)
        assert isinstance(turtle_str, str)
        # Should still be parseable (empty graph)
        g = rdflib.Graph()
        g.parse(data=turtle_str, format="turtle")

    def test_roundtrip_triple_count_matches_jsonld(self) -> None:
        """Turtle and JSON-LD should produce the same number of triples."""
        env = _sample_aas_env()
        jsonld = aas_to_jsonld(env)

        g_jsonld = rdflib.Graph()
        g_jsonld.parse(data=json.dumps(jsonld), format="json-ld")

        g_turtle = rdflib.Graph()
        g_turtle.parse(data=aas_to_turtle(env), format="turtle")

        assert len(g_turtle) == len(g_jsonld)
