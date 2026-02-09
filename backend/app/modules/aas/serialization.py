"""AAS environment serialization to JSON-LD, Turtle (RDF), and XML formats.

Provides conversion from AAS environment dicts to:
- **JSON-LD** using rdflib for Linked Data interoperability
- **Turtle** (RDF) via rdflib graph serialization
- **XML** using BaSyx's built-in XML serializer
"""

from __future__ import annotations

import io
import json
from typing import Any

import rdflib
from basyx.aas import model
from basyx.aas.adapter import json as basyx_json
from basyx.aas.adapter import xml as basyx_xml

from app.core.logging import get_logger
from app.modules.aas.references import extract_semantic_id_str

logger = get_logger(__name__)

# AAS / W3C context URIs for JSON-LD output
_AAS_CONTEXT = "https://www.w3.org/2019/wot/td/v1"
_AAS_NAMESPACE = "https://admin-shell.io/aas/3/0/"

# Mapping from AAS JSON modelType names to RDF type URIs
_MODEL_TYPE_TO_RDF: dict[str, str] = {
    "AssetAdministrationShell": f"{_AAS_NAMESPACE}AssetAdministrationShell",
    "Submodel": f"{_AAS_NAMESPACE}Submodel",
    "SubmodelElementCollection": f"{_AAS_NAMESPACE}SubmodelElementCollection",
    "SubmodelElementList": f"{_AAS_NAMESPACE}SubmodelElementList",
    "Property": f"{_AAS_NAMESPACE}Property",
    "MultiLanguageProperty": f"{_AAS_NAMESPACE}MultiLanguageProperty",
    "Range": f"{_AAS_NAMESPACE}Range",
    "File": f"{_AAS_NAMESPACE}File",
    "Blob": f"{_AAS_NAMESPACE}Blob",
    "Entity": f"{_AAS_NAMESPACE}Entity",
    "ReferenceElement": f"{_AAS_NAMESPACE}ReferenceElement",
    "RelationshipElement": f"{_AAS_NAMESPACE}RelationshipElement",
    "AnnotatedRelationshipElement": (f"{_AAS_NAMESPACE}AnnotatedRelationshipElement"),
    "Operation": f"{_AAS_NAMESPACE}Operation",
    "Capability": f"{_AAS_NAMESPACE}Capability",
    "BasicEventElement": f"{_AAS_NAMESPACE}BasicEventElement",
    "ConceptDescription": f"{_AAS_NAMESPACE}ConceptDescription",
}


def aas_to_jsonld(aas_env: dict[str, Any]) -> dict[str, Any]:
    """Convert an AAS environment dict to a JSON-LD document.

    The output uses the W3C Web of Things context as a base and maps
    AAS types to their RDF equivalents under the AAS 3.0 namespace.

    Args:
        aas_env: AAS environment as a JSON-compatible dict.

    Returns:
        A JSON-LD document (dict) with ``@context``, ``@type``, and
        ``@graph`` containing all identifiable elements.
    """
    graph: list[dict[str, Any]] = []

    # Process AAS shells
    for shell in aas_env.get("assetAdministrationShells", []):
        node = _identifiable_to_node(shell, "AssetAdministrationShell")
        asset_info = shell.get("assetInformation")
        if isinstance(asset_info, dict):
            node["aas:assetInformation"] = {
                "aas:assetKind": asset_info.get("assetKind"),
                "aas:globalAssetId": asset_info.get("globalAssetId"),
            }
        graph.append(node)

    # Process submodels
    for sm in aas_env.get("submodels", []):
        node = _identifiable_to_node(sm, "Submodel")
        elements = sm.get("submodelElements", [])
        if elements:
            node["aas:submodelElements"] = [_element_to_node(el) for el in elements]
        graph.append(node)

    # Process concept descriptions
    for cd in aas_env.get("conceptDescriptions", []):
        node = _identifiable_to_node(cd, "ConceptDescription")
        graph.append(node)

    return {
        "@context": {
            "td": _AAS_CONTEXT,
            "aas": _AAS_NAMESPACE,
        },
        "@type": "aas:Environment",
        "@graph": graph,
    }


def aas_to_turtle(aas_env: dict[str, Any]) -> str:
    """Convert an AAS environment dict to Turtle (RDF) format.

    Generates JSON-LD first, then parses it into an rdflib graph and
    serializes as Turtle.  This reuses the JSON-LD mapping so that the
    resulting RDF triples are identical regardless of the output format.

    Args:
        aas_env: AAS environment as a JSON-compatible dict.

    Returns:
        A Turtle-serialized string of the RDF graph.
    """
    jsonld = aas_to_jsonld(aas_env)
    jsonld_str = json.dumps(jsonld)
    g = rdflib.Graph()
    g.parse(data=jsonld_str, format="json-ld")
    result: str = g.serialize(format="turtle")
    return result


def aas_to_xml(aas_env: dict[str, Any]) -> bytes:
    """Convert an AAS environment dict to AAS XML format.

    Uses BaSyx's built-in XML serializer after deserializing the dict
    through BaSyx's JSON reader.

    Args:
        aas_env: AAS environment as a JSON-compatible dict.

    Returns:
        XML-encoded bytes with AAS Part 1 namespaces.
    """
    payload = json.dumps(aas_env, sort_keys=True, ensure_ascii=False)
    string_io = io.StringIO(payload)
    try:
        store: model.DictObjectStore[model.Identifiable] = basyx_json.read_aas_json_file(  # type: ignore[attr-defined]
            string_io,
            failsafe=True,
        )
    finally:
        string_io.close()

    xml_buffer = io.BytesIO()
    basyx_xml.write_aas_xml_file(xml_buffer, store)  # type: ignore[attr-defined]
    xml_buffer.seek(0)
    return xml_buffer.read()


def _identifiable_to_node(
    obj: dict[str, Any],
    model_type: str,
) -> dict[str, Any]:
    """Build a JSON-LD node for an identifiable AAS element."""
    rdf_type = _MODEL_TYPE_TO_RDF.get(model_type, f"{_AAS_NAMESPACE}{model_type}")
    node: dict[str, Any] = {
        "@type": rdf_type,
    }
    obj_id = obj.get("id")
    if obj_id:
        node["@id"] = str(obj_id)
    id_short = obj.get("idShort")
    if id_short:
        node["aas:idShort"] = id_short

    sem_id = extract_semantic_id_str(obj)
    if sem_id:
        node["aas:semanticId"] = sem_id

    return node


def _reference_to_ld(ref: dict[str, Any]) -> dict[str, Any]:
    """Convert an AAS Reference dict to a JSON-LD representation."""
    ld: dict[str, Any] = {"@type": f"{_AAS_NAMESPACE}Reference"}
    ref_type = ref.get("type")
    if ref_type:
        ld["aas:type"] = ref_type
    keys = ref.get("keys")
    if isinstance(keys, list):
        ld["aas:keys"] = keys
    return ld


def _element_to_node(element: dict[str, Any]) -> dict[str, Any]:
    """Build a JSON-LD node for a submodel element.

    Dispatches on ``modelType`` to handle type-specific fields correctly.
    """
    model_type = element.get("modelType", "SubmodelElement")
    rdf_type = _MODEL_TYPE_TO_RDF.get(model_type, f"{_AAS_NAMESPACE}{model_type}")
    node: dict[str, Any] = {
        "@type": rdf_type,
    }

    id_short = element.get("idShort")
    if id_short:
        node["aas:idShort"] = id_short

    sem_id = extract_semantic_id_str(element)
    if sem_id:
        node["aas:semanticId"] = sem_id

    # --- type-specific handling ---
    if model_type == "SubmodelElementCollection":
        children = element.get("value")
        if isinstance(children, list):
            node["aas:value"] = [_element_to_node(c) for c in children]

    elif model_type == "SubmodelElementList":
        items = element.get("value")
        if isinstance(items, list):
            converted: list[Any] = []
            for item in items:
                if isinstance(item, dict) and "modelType" in item:
                    converted.append(_element_to_node(item))
                else:
                    converted.append(item)
            node["aas:value"] = converted

    elif model_type == "Entity":
        statements = element.get("statements")
        if isinstance(statements, list):
            node["aas:statements"] = [_element_to_node(s) for s in statements]
        entity_type = element.get("entityType")
        if entity_type is not None:
            node["aas:entityType"] = entity_type
        global_asset_id = element.get("globalAssetId")
        if global_asset_id is not None:
            node["aas:globalAssetId"] = global_asset_id

    elif model_type == "RelationshipElement":
        first = element.get("first")
        if isinstance(first, dict):
            node["aas:first"] = _reference_to_ld(first)
        second = element.get("second")
        if isinstance(second, dict):
            node["aas:second"] = _reference_to_ld(second)

    elif model_type == "AnnotatedRelationshipElement":
        first = element.get("first")
        if isinstance(first, dict):
            node["aas:first"] = _reference_to_ld(first)
        second = element.get("second")
        if isinstance(second, dict):
            node["aas:second"] = _reference_to_ld(second)
        annotations = element.get("annotations")
        if isinstance(annotations, list):
            node["aas:annotations"] = [_element_to_node(a) for a in annotations]

    elif model_type == "MultiLanguageProperty":
        value = element.get("value")
        if value is not None:
            node["aas:value"] = value

    elif model_type == "Range":
        min_val = element.get("min")
        if min_val is not None:
            node["aas:min"] = min_val
        max_val = element.get("max")
        if max_val is not None:
            node["aas:max"] = max_val

    elif model_type in ("File", "Blob"):
        value = element.get("value")
        if value is not None:
            node["aas:value"] = value
        content_type = element.get("contentType")
        if content_type is not None:
            node["aas:contentType"] = content_type

    else:
        # Property, ReferenceElement, and other simple types
        value = element.get("value")
        if value is not None:
            node["aas:value"] = value

    return node
