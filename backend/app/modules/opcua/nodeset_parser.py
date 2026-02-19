"""OPC UA NodeSet2.xml parser using lxml.

Extracts namespace URIs, node metadata, engineering units, and builds
a JSONB-ready node graph for storage and search.

Usage::

    parsed = parse_nodeset_xml(xml_bytes)
    # parsed.namespace_uris, parsed.nodes, parsed.node_graph, parsed.summary
"""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from lxml import etree

# OPC UA NodeSet2 XML namespace
_UA_NS = "http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"
_NS_MAP = {"ua": _UA_NS}

# Node element tags we extract
_NODE_TAGS = frozenset(
    {
        f"{{{_UA_NS}}}UAObject",
        f"{{{_UA_NS}}}UAVariable",
        f"{{{_UA_NS}}}UADataType",
        f"{{{_UA_NS}}}UAReferenceType",
        f"{{{_UA_NS}}}UAObjectType",
        f"{{{_UA_NS}}}UAVariableType",
        f"{{{_UA_NS}}}UAMethod",
        f"{{{_UA_NS}}}UAView",
    }
)

# Map tag to short node class label
_TAG_TO_CLASS: dict[str, str] = {
    f"{{{_UA_NS}}}UAObject": "Object",
    f"{{{_UA_NS}}}UAVariable": "Variable",
    f"{{{_UA_NS}}}UADataType": "DataType",
    f"{{{_UA_NS}}}UAReferenceType": "ReferenceType",
    f"{{{_UA_NS}}}UAObjectType": "ObjectType",
    f"{{{_UA_NS}}}UAVariableType": "VariableType",
    f"{{{_UA_NS}}}UAMethod": "Method",
    f"{{{_UA_NS}}}UAView": "View",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ParsedNode:
    """Single node extracted from a NodeSet."""

    node_id: str
    browse_name: str
    node_class: str
    data_type: str | None = None
    description: str | None = None
    engineering_unit: str | None = None
    parent_node_id: str | None = None
    namespace_index: int = 0


@dataclass
class ParsedNodeSet:
    """Complete parsed result from a NodeSet2.xml file."""

    namespace_uris: list[str] = field(default_factory=list)
    nodeset_version: str | None = None
    publication_date: date | None = None
    nodes: list[ParsedNode] = field(default_factory=list)
    node_graph: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    sha256: str = ""


# ---------------------------------------------------------------------------
# Parser internals
# ---------------------------------------------------------------------------


def _extract_namespace_uris(root: etree._Element) -> list[str]:
    """Extract NamespaceUris from the nodeset header."""
    uris: list[str] = []
    ns_elem = root.find("ua:NamespaceUris", _NS_MAP)
    if ns_elem is not None:
        for uri_elem in ns_elem.findall("ua:Uri", _NS_MAP):
            if uri_elem.text:
                uris.append(uri_elem.text.strip())
    return uris


def _extract_description(node_elem: etree._Element) -> str | None:
    """Extract first Description text from a node element."""
    desc = node_elem.find("ua:Description", _NS_MAP)
    if desc is not None and desc.text:
        return desc.text.strip()
    return None


def _extract_engineering_unit(node_elem: etree._Element) -> str | None:
    """Extract engineering unit from EUInformation extension, if present.

    The engineering unit lives in:
      <Extensions><Extension>...<EUInformation>...<DisplayName>...<Text>
    or in the value of a Variable with DataType=EUInformation.
    """
    # Try the direct approach via any nested EUInformation-like element
    for ext in node_elem.iter():
        tag = ext.tag if isinstance(ext.tag, str) else ""
        # Look for DisplayName inside EUInformation structures
        if tag.endswith("}DisplayName") or tag == "DisplayName":
            text_elem = ext.find(f"{{{_UA_NS}}}Text") if _UA_NS in tag else ext.find("Text")
            if text_elem is not None and text_elem.text:
                return text_elem.text.strip()
            if ext.text and ext.text.strip():
                return ext.text.strip()
    return None


def _resolve_parent(node_elem: etree._Element) -> str | None:
    """Find the parent NodeId via HasComponent/HasProperty/Organizes references."""
    refs_container = node_elem.find("ua:References", _NS_MAP)
    if refs_container is None:
        return None
    for ref in refs_container.findall("ua:Reference", _NS_MAP):
        ref_type = ref.get("ReferenceType", "")
        is_forward = ref.get("IsForward", "true").lower()
        # Inverse hierarchical references point to the parent
        if (
            is_forward == "false"
            and ref_type
            in (
                "HasComponent",
                "HasProperty",
                "Organizes",
                "HasSubtype",
            )
            and ref.text
        ):
            return ref.text.strip()
    return None


def _parse_node_id_ns(node_id: str) -> int:
    """Extract namespace index from a NodeId string like 'ns=4;s=Foo'."""
    if node_id.startswith("ns="):
        try:
            return int(node_id.split(";")[0].removeprefix("ns="))
        except (ValueError, IndexError):
            pass
    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_nodeset_xml(xml_bytes: bytes) -> ParsedNodeSet:
    """Parse a NodeSet2.xml file and return structured metadata.

    Args:
        xml_bytes: Raw XML content.

    Returns:
        ParsedNodeSet with extracted nodes, graph, summary, and SHA-256.

    Raises:
        etree.XMLSyntaxError: If the XML is malformed.
        ValueError: If the document lacks required NodeSet2 structure.
    """
    sha256 = hashlib.sha256(xml_bytes).hexdigest()

    root = etree.fromstring(xml_bytes)  # noqa: S320 — trusted input

    # Validate root element
    root_tag = root.tag
    if not (root_tag.endswith("}UANodeSet") or root_tag == "UANodeSet"):
        raise ValueError(f"Root element is '{root_tag}', expected UANodeSet")

    # Header metadata
    namespace_uris = _extract_namespace_uris(root)

    # Model element for version/date
    nodeset_version: str | None = None
    publication_date: date | None = None
    models = root.find("ua:Models", _NS_MAP)
    if models is not None:
        model = models.find("ua:Model", _NS_MAP)
        if model is not None:
            nodeset_version = model.get("Version")
            pub_date_str = model.get("PublicationDate")
            if pub_date_str:
                with contextlib.suppress(ValueError):
                    publication_date = date.fromisoformat(pub_date_str[:10])

    # Extract nodes
    nodes: list[ParsedNode] = []
    class_counts: dict[str, int] = {}

    for elem in root:
        if elem.tag not in _NODE_TAGS:
            continue

        node_class = _TAG_TO_CLASS.get(elem.tag, "Unknown")
        node_id = elem.get("NodeId", "")
        browse_name = elem.get("BrowseName", "")
        data_type = elem.get("DataType")

        parsed = ParsedNode(
            node_id=node_id,
            browse_name=browse_name,
            node_class=node_class,
            data_type=data_type,
            description=_extract_description(elem),
            engineering_unit=_extract_engineering_unit(elem) if node_class == "Variable" else None,
            parent_node_id=_resolve_parent(elem),
            namespace_index=_parse_node_id_ns(node_id),
        )
        nodes.append(parsed)
        class_counts[node_class] = class_counts.get(node_class, 0) + 1

    # Build node graph: grouped by namespace URI
    node_graph: dict[str, dict[str, dict[str, Any]]] = {}
    for node in nodes:
        # Resolve namespace URI from index
        ns_uri = (
            namespace_uris[node.namespace_index - 1]
            if 0 < node.namespace_index <= len(namespace_uris)
            else "http://opcfoundation.org/UA/"
        )
        if ns_uri not in node_graph:
            node_graph[ns_uri] = {}

        entry: dict[str, Any] = {
            "browse_name": node.browse_name,
            "node_class": node.node_class,
        }
        if node.data_type:
            entry["data_type"] = node.data_type
        if node.description:
            entry["description"] = node.description
        if node.engineering_unit:
            entry["engineering_unit"] = node.engineering_unit
        if node.parent_node_id:
            entry["parent_node_id"] = node.parent_node_id

        node_graph[ns_uri][node.node_id] = entry

    summary = {
        "object_count": class_counts.get("Object", 0),
        "variable_count": class_counts.get("Variable", 0),
        "datatype_count": class_counts.get("DataType", 0),
        "reference_type_count": class_counts.get("ReferenceType", 0),
        "object_type_count": class_counts.get("ObjectType", 0),
        "variable_type_count": class_counts.get("VariableType", 0),
        "method_count": class_counts.get("Method", 0),
        "total_nodes": len(nodes),
    }

    return ParsedNodeSet(
        namespace_uris=namespace_uris,
        nodeset_version=nodeset_version,
        publication_date=publication_date,
        nodes=nodes,
        node_graph=node_graph,
        summary=summary,
        sha256=sha256,
    )
