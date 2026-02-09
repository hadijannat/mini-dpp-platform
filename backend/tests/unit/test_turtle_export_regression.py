"""Regression tests for Turtle (RDF) export via aas_to_turtle().

Validates that all AAS element types serialize correctly through the
JSON-LD → rdflib → Turtle pipeline without crashing.
"""

from __future__ import annotations

from typing import Any

from app.modules.aas.serialization import (
    _element_to_node,
    _reference_to_ld,
    aas_to_turtle,
)


def _full_aas_env() -> dict[str, Any]:
    """Return an AAS environment containing all element types."""
    return {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:aas:regression:1",
                "idShort": "RegressionAAS",
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": "urn:asset:regression:1",
                },
            }
        ],
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:regression:1",
                "idShort": "AllElementTypes",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": "urn:example:all-types"}],
                },
                "submodelElements": [
                    {
                        "idShort": "StringProp",
                        "modelType": "Property",
                        "valueType": "xs:string",
                        "value": "hello",
                    },
                    {
                        "idShort": "NumericProp",
                        "modelType": "Property",
                        "valueType": "xs:integer",
                        "value": "42",
                    },
                    {
                        "idShort": "ManufacturerName",
                        "modelType": "MultiLanguageProperty",
                        "value": [
                            {"language": "en", "text": "ACME Corp"},
                            {"language": "de", "text": "ACME GmbH"},
                        ],
                    },
                    {
                        "idShort": "TemperatureRange",
                        "modelType": "Range",
                        "valueType": "xs:double",
                        "min": "-40.0",
                        "max": "85.0",
                    },
                    {
                        "idShort": "ManualFile",
                        "modelType": "File",
                        "contentType": "application/pdf",
                        "value": "/docs/manual.pdf",
                    },
                    {
                        "idShort": "FirmwareBlob",
                        "modelType": "Blob",
                        "contentType": "application/octet-stream",
                        "value": "AQIDBA==",
                    },
                    {
                        "idShort": "NestedCollection",
                        "modelType": "SubmodelElementCollection",
                        "value": [
                            {
                                "idShort": "InnerProp",
                                "modelType": "Property",
                                "valueType": "xs:string",
                                "value": "inner-value",
                            },
                        ],
                    },
                    {
                        "idShort": "PrimitiveList",
                        "modelType": "SubmodelElementList",
                        "typeValueListElement": "Property",
                        "value": ["item-a", "item-b", "item-c"],
                    },
                    {
                        "idShort": "ObjectList",
                        "modelType": "SubmodelElementList",
                        "typeValueListElement": "SubmodelElementCollection",
                        "value": [
                            {
                                "idShort": "ListEntry0",
                                "modelType": "SubmodelElementCollection",
                                "value": [
                                    {
                                        "idShort": "EntryProp",
                                        "modelType": "Property",
                                        "valueType": "xs:string",
                                        "value": "list-entry-val",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "idShort": "DeviceEntity",
                        "modelType": "Entity",
                        "entityType": "SelfManagedEntity",
                        "globalAssetId": "urn:asset:device:1",
                        "statements": [
                            {
                                "idShort": "DeviceSerial",
                                "modelType": "Property",
                                "valueType": "xs:string",
                                "value": "DEV-001",
                            }
                        ],
                    },
                    {
                        "idShort": "PartRelation",
                        "modelType": "RelationshipElement",
                        "first": {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": "urn:sm:regression:1"}],
                        },
                        "second": {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": "urn:sm:other:1"}],
                        },
                    },
                    {
                        "idShort": "AnnotatedPartRelation",
                        "modelType": "AnnotatedRelationshipElement",
                        "first": {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": "urn:sm:regression:1"}],
                        },
                        "second": {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": "urn:sm:other:2"}],
                        },
                        "annotations": [
                            {
                                "idShort": "Annotation1",
                                "modelType": "Property",
                                "valueType": "xs:string",
                                "value": "note",
                            }
                        ],
                    },
                    {
                        "idShort": "RefElement",
                        "modelType": "ReferenceElement",
                        "value": {
                            "type": "ModelReference",
                            "keys": [{"type": "Submodel", "value": "urn:sm:referenced:1"}],
                        },
                    },
                    {
                        "idShort": "CalcOperation",
                        "modelType": "Operation",
                        "inputVariables": [
                            {"idShort": "X", "modelType": "Property", "value": "1"},
                        ],
                        "outputVariables": [
                            {"idShort": "Y", "modelType": "Property", "value": "2"},
                        ],
                    },
                    {
                        "idShort": "TempEvent",
                        "modelType": "BasicEventElement",
                        "observed": {
                            "type": "ModelReference",
                            "keys": [{"type": "Property", "value": "Temperature"}],
                        },
                        "direction": "output",
                        "state": "on",
                    },
                    {
                        "idShort": "HeatCapability",
                        "modelType": "Capability",
                    },
                ],
            }
        ],
        "conceptDescriptions": [],
    }


class TestTurtleRoundTrip:
    def test_produces_valid_turtle_string(self) -> None:
        result = aas_to_turtle(_full_aas_env())
        assert isinstance(result, str)
        assert len(result) > 0
        assert "aas" in result.lower() or "@prefix" in result

    def test_no_crash_on_primitive_list_items(self) -> None:
        """The original crash case: SubmodelElementList with string items."""
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:primitive-list",
                    "idShort": "PrimitiveListTest",
                    "submodelElements": [
                        {
                            "idShort": "Codes",
                            "modelType": "SubmodelElementList",
                            "value": ["ABC", "DEF", "GHI"],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)

    def test_handles_entity_with_statements(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:entity-test",
                    "idShort": "EntityTest",
                    "submodelElements": [
                        {
                            "idShort": "MyEntity",
                            "modelType": "Entity",
                            "entityType": "SelfManagedEntity",
                            "globalAssetId": "urn:asset:ent:1",
                            "statements": [
                                {
                                    "idShort": "StateProp",
                                    "modelType": "Property",
                                    "valueType": "xs:string",
                                    "value": "active",
                                }
                            ],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert "MyEntity" in result or "entity" in result.lower()

    def test_handles_relationship_elements(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:rel-test",
                    "idShort": "RelTest",
                    "submodelElements": [
                        {
                            "idShort": "Rel1",
                            "modelType": "RelationshipElement",
                            "first": {
                                "type": "ModelReference",
                                "keys": [{"type": "Submodel", "value": "urn:sm:a"}],
                            },
                            "second": {
                                "type": "ModelReference",
                                "keys": [{"type": "Submodel", "value": "urn:sm:b"}],
                            },
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_annotated_relationship(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:annrel-test",
                    "idShort": "AnnRelTest",
                    "submodelElements": [
                        {
                            "idShort": "AnnRel1",
                            "modelType": "AnnotatedRelationshipElement",
                            "first": {
                                "type": "ModelReference",
                                "keys": [{"type": "Submodel", "value": "urn:sm:a"}],
                            },
                            "second": {
                                "type": "ModelReference",
                                "keys": [{"type": "Submodel", "value": "urn:sm:b"}],
                            },
                            "annotations": [
                                {
                                    "idShort": "Note",
                                    "modelType": "Property",
                                    "valueType": "xs:string",
                                    "value": "test-annotation",
                                }
                            ],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)

    def test_handles_multilang_property(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:mlp-test",
                    "idShort": "MLPTest",
                    "submodelElements": [
                        {
                            "idShort": "MLP1",
                            "modelType": "MultiLanguageProperty",
                            "value": [
                                {"language": "en", "text": "Hello"},
                                {"language": "de", "text": "Hallo"},
                            ],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)

    def test_handles_range_element(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:range-test",
                    "idShort": "RangeTest",
                    "submodelElements": [
                        {
                            "idShort": "Rng1",
                            "modelType": "Range",
                            "valueType": "xs:double",
                            "min": "0",
                            "max": "100",
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)

    def test_handles_file_and_blob(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:fileblob-test",
                    "idShort": "FileBlobTest",
                    "submodelElements": [
                        {
                            "idShort": "Doc",
                            "modelType": "File",
                            "contentType": "application/pdf",
                            "value": "/docs/file.pdf",
                        },
                        {
                            "idShort": "BinData",
                            "modelType": "Blob",
                            "contentType": "application/octet-stream",
                            "value": "AQID",
                        },
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)

    def test_turtle_contains_submodel_references(self) -> None:
        result = aas_to_turtle(_full_aas_env())
        # The submodel ID should appear in the Turtle output
        assert "urn:sm:regression:1" in result

    def test_no_crash_on_idta_placeholder_braces(self) -> None:
        """IDTA templates use placeholder URIs like ``{arbitrary}`` in concept
        description IDs.  Curly braces are invalid in N3/Turtle syntax; the
        serializer must encode them so rdflib can produce valid output."""
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:placeholder-test",
                    "idShort": "PlaceholderTest",
                    "submodelElements": [],
                }
            ],
            "conceptDescriptions": [
                {
                    "id": "https://admin-shell.io/IDTA/TechnicalData/{arbitrary}/2/0",
                    "idShort": "ArbitraryCd",
                },
            ],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)
        assert len(result) > 0
        # Curly braces must be percent-encoded in the output
        assert "%7B" in result or "%7b" in result
        assert "{arbitrary}" not in result

    def test_jsonld_encodes_braces_in_ids(self) -> None:
        """JSON-LD output must also percent-encode braces in @id values."""
        from app.modules.aas.serialization import aas_to_jsonld

        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [],
            "conceptDescriptions": [
                {
                    "id": "https://admin-shell.io/IDTA/Data/{placeholder}/1/0",
                    "idShort": "PlaceholderCD",
                },
            ],
        }
        result = aas_to_jsonld(env)
        cds = [n for n in result["@graph"] if "ConceptDescription" in n.get("@type", "")]
        assert len(cds) == 1
        assert "%7B" in cds[0]["@id"]
        assert "{placeholder}" not in cds[0]["@id"]

    def test_encodes_braces_in_all_identifiable_types(self) -> None:
        """Brace encoding applies to shells, submodels, AND concept descriptions."""
        env: dict[str, Any] = {
            "assetAdministrationShells": [
                {
                    "id": "urn:aas:{dev}:1",
                    "idShort": "DevAAS",
                    "assetInformation": {"assetKind": "Instance"},
                }
            ],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:{version}/test",
                    "idShort": "VersionedSM",
                    "submodelElements": [],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert "{dev}" not in result
        assert "{version}" not in result
        assert "%7B" in result or "%7b" in result

    def test_does_not_encode_valid_uri_characters(self) -> None:
        """Normal URIs and URNs must pass through unmodified."""
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:nameplate:v2.0",
                    "idShort": "Nameplate",
                    "submodelElements": [],
                }
            ],
            "conceptDescriptions": [
                {
                    "id": "https://admin-shell.io/IDTA/TechnicalData/Spec/2/0",
                    "idShort": "ValidCD",
                },
            ],
        }
        result = aas_to_turtle(env)
        assert "urn:sm:nameplate:v2.0" in result
        assert "https://admin-shell.io/IDTA/TechnicalData/Spec/2/0" in result


class TestElementToNode:
    def test_property_simple_value(self) -> None:
        node = _element_to_node({"idShort": "Prop1", "modelType": "Property", "value": "hello"})
        assert node["aas:value"] == "hello"
        assert "Property" in node["@type"]

    def test_multilang_property_preserves_list(self) -> None:
        mlp_value = [{"language": "en", "text": "Hello"}]
        node = _element_to_node(
            {"idShort": "MLP", "modelType": "MultiLanguageProperty", "value": mlp_value}
        )
        assert node["aas:value"] == mlp_value

    def test_collection_recurses(self) -> None:
        node = _element_to_node(
            {
                "idShort": "Col",
                "modelType": "SubmodelElementCollection",
                "value": [{"idShort": "Inner", "modelType": "Property", "value": "v"}],
            }
        )
        children = node["aas:value"]
        assert len(children) == 1
        assert children[0]["aas:idShort"] == "Inner"

    def test_list_with_primitives(self) -> None:
        node = _element_to_node(
            {
                "idShort": "PrimList",
                "modelType": "SubmodelElementList",
                "value": ["a", "b", "c"],
            }
        )
        assert node["aas:value"] == ["a", "b", "c"]

    def test_list_with_dict_items(self) -> None:
        node = _element_to_node(
            {
                "idShort": "ObjList",
                "modelType": "SubmodelElementList",
                "value": [{"idShort": "Entry0", "modelType": "Property", "value": "x"}],
            }
        )
        items = node["aas:value"]
        assert len(items) == 1
        assert items[0]["aas:idShort"] == "Entry0"

    def test_entity_with_statements(self) -> None:
        node = _element_to_node(
            {
                "idShort": "Ent",
                "modelType": "Entity",
                "entityType": "SelfManagedEntity",
                "globalAssetId": "urn:asset:1",
                "statements": [{"idShort": "S1", "modelType": "Property", "value": "v"}],
            }
        )
        assert node["aas:entityType"] == "SelfManagedEntity"
        assert node["aas:globalAssetId"] == "urn:asset:1"
        assert len(node["aas:statements"]) == 1

    def test_relationship_element(self) -> None:
        first_ref = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "a"}]}
        second_ref = {"type": "ModelReference", "keys": [{"type": "Submodel", "value": "b"}]}
        node = _element_to_node(
            {
                "idShort": "Rel",
                "modelType": "RelationshipElement",
                "first": first_ref,
                "second": second_ref,
            }
        )
        assert "aas:first" in node
        assert "aas:second" in node

    def test_annotated_relationship(self) -> None:
        node = _element_to_node(
            {
                "idShort": "AnnRel",
                "modelType": "AnnotatedRelationshipElement",
                "first": {"type": "ModelReference", "keys": []},
                "second": {"type": "ModelReference", "keys": []},
                "annotations": [{"idShort": "A1", "modelType": "Property", "value": "n"}],
            }
        )
        assert len(node["aas:annotations"]) == 1

    def test_range_element(self) -> None:
        node = _element_to_node(
            {
                "idShort": "Rng",
                "modelType": "Range",
                "min": "0",
                "max": "100",
            }
        )
        assert node["aas:min"] == "0"
        assert node["aas:max"] == "100"
        assert "aas:value" not in node

    def test_file_element(self) -> None:
        node = _element_to_node(
            {
                "idShort": "F1",
                "modelType": "File",
                "contentType": "application/pdf",
                "value": "/path/file.pdf",
            }
        )
        assert node["aas:value"] == "/path/file.pdf"
        assert node["aas:contentType"] == "application/pdf"

    def test_blob_element(self) -> None:
        node = _element_to_node(
            {
                "idShort": "B1",
                "modelType": "Blob",
                "contentType": "application/octet-stream",
                "value": "AQID",
            }
        )
        assert node["aas:value"] == "AQID"
        assert node["aas:contentType"] == "application/octet-stream"


class TestReferenceToLD:
    def test_basic_reference(self) -> None:
        ref = {
            "type": "ModelReference",
            "keys": [{"type": "Submodel", "value": "urn:sm:1"}],
        }
        ld = _reference_to_ld(ref)
        assert ld["aas:type"] == "ModelReference"
        assert len(ld["aas:keys"]) == 1

    def test_empty_keys(self) -> None:
        ref = {"type": "ExternalReference", "keys": []}
        ld = _reference_to_ld(ref)
        assert ld["aas:keys"] == []

    def test_missing_type(self) -> None:
        ref = {"keys": [{"type": "Submodel", "value": "urn:sm:1"}]}
        ld = _reference_to_ld(ref)
        assert "aas:type" not in ld
        assert "aas:keys" in ld


class TestOperationElement:
    """Tests for Operation element serialization (C-2 fix)."""

    def test_operation_with_all_variable_kinds(self) -> None:
        node = _element_to_node(
            {
                "idShort": "CalcOp",
                "modelType": "Operation",
                "inputVariables": [{"idShort": "Input1", "modelType": "Property", "value": "10"}],
                "outputVariables": [{"idShort": "Output1", "modelType": "Property", "value": "20"}],
                "inoutputVariables": [
                    {"idShort": "InOut1", "modelType": "Property", "value": "30"}
                ],
            }
        )
        assert "Operation" in node["@type"]
        assert len(node["aas:inputVariables"]) == 1
        assert node["aas:inputVariables"][0]["aas:idShort"] == "Input1"
        assert len(node["aas:outputVariables"]) == 1
        assert len(node["aas:inoutputVariables"]) == 1
        # Operation should NOT have a generic aas:value
        assert "aas:value" not in node

    def test_operation_with_no_variables(self) -> None:
        node = _element_to_node({"idShort": "EmptyOp", "modelType": "Operation"})
        assert "Operation" in node["@type"]
        assert "aas:inputVariables" not in node
        assert "aas:outputVariables" not in node
        assert "aas:inoutputVariables" not in node

    def test_operation_turtle_round_trip(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:operation-test",
                    "idShort": "OperationTest",
                    "submodelElements": [
                        {
                            "idShort": "Calculate",
                            "modelType": "Operation",
                            "inputVariables": [
                                {"idShort": "X", "modelType": "Property", "value": "5"}
                            ],
                            "outputVariables": [
                                {"idShort": "Y", "modelType": "Property", "value": "10"}
                            ],
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)
        assert len(result) > 0


class TestBasicEventElement:
    """Tests for BasicEventElement serialization (C-2 fix)."""

    def test_basic_event_element_full(self) -> None:
        node = _element_to_node(
            {
                "idShort": "TempEvent",
                "modelType": "BasicEventElement",
                "observed": {
                    "type": "ModelReference",
                    "keys": [{"type": "Property", "value": "Temperature"}],
                },
                "direction": "output",
                "state": "on",
                "messageBroker": {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": "mqtt://broker:1883"}],
                },
            }
        )
        assert "BasicEventElement" in node["@type"]
        assert node["aas:direction"] == "output"
        assert node["aas:state"] == "on"
        assert "Reference" in node["aas:observed"]["@type"]
        assert "Reference" in node["aas:messageBroker"]["@type"]
        # Should NOT have a generic aas:value
        assert "aas:value" not in node

    def test_basic_event_element_minimal(self) -> None:
        node = _element_to_node(
            {
                "idShort": "MinEvent",
                "modelType": "BasicEventElement",
                "observed": {
                    "type": "ModelReference",
                    "keys": [{"type": "Property", "value": "Sensor"}],
                },
                "direction": "input",
                "state": "on",
            }
        )
        assert node["aas:direction"] == "input"
        assert "aas:messageBroker" not in node

    def test_basic_event_element_turtle_round_trip(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:event-test",
                    "idShort": "EventTest",
                    "submodelElements": [
                        {
                            "idShort": "SensorEvent",
                            "modelType": "BasicEventElement",
                            "observed": {
                                "type": "ModelReference",
                                "keys": [{"type": "Property", "value": "Temp"}],
                            },
                            "direction": "output",
                            "state": "on",
                        }
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)
        assert len(result) > 0


class TestCapabilityElement:
    """Tests for Capability element serialization (C-2 fix)."""

    def test_capability_no_extra_fields(self) -> None:
        node = _element_to_node({"idShort": "Cap1", "modelType": "Capability"})
        assert "Capability" in node["@type"]
        assert node["aas:idShort"] == "Cap1"
        # Capability has no structural fields beyond type and idShort
        assert "aas:value" not in node

    def test_capability_turtle_round_trip(self) -> None:
        env: dict[str, Any] = {
            "assetAdministrationShells": [],
            "submodels": [
                {
                    "modelType": "Submodel",
                    "id": "urn:sm:capability-test",
                    "idShort": "CapabilityTest",
                    "submodelElements": [
                        {"idShort": "CanHeat", "modelType": "Capability"},
                    ],
                }
            ],
            "conceptDescriptions": [],
        }
        result = aas_to_turtle(env)
        assert isinstance(result, str)
        assert len(result) > 0
