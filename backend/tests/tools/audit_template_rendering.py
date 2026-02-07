"""Audit template rendering accuracy across the full pipeline.

Fetches each IDTA template, runs it through the same pipeline as the /contract
endpoint (BaSyx parse → definition AST → JSON Schema), then produces a
per-template element inventory showing:
  - Every element's path, modelType, depth, and frontend renderer mapping
  - Schema coverage (does a JSON Schema node exist for each definition element?)
  - ReadOnly elements and whether that classification is appropriate
  - Empty lists, childless collections, statement-less entities
  - Overall "editable coverage" percentage

Usage:
    cd backend
    uv run python tests/tools/audit_template_rendering.py
    uv run python tests/tools/audit_template_rendering.py --json  # write audit_report.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Add backend to path so we can import app modules
backend_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_dir))

from app.modules.templates.basyx_parser import BasyxTemplateParser  # noqa: E402
from app.modules.templates.catalog import TEMPLATE_CATALOG  # noqa: E402
from app.modules.templates.definition import TemplateDefinitionBuilder  # noqa: E402
from app.modules.templates.schema_from_definition import (  # noqa: E402
    DefinitionToSchemaConverter,
)
from tests.tools.compute_golden_hashes import fetch_template_json  # noqa: E402

REPORT_PATH = backend_dir / "tests" / "tools" / "audit_report.json"
GOLDENS_DIR = backend_dir / "tests" / "goldens" / "templates"

# ── Frontend renderer mapping (mirrors AASRenderer.tsx) ──────────────────

RENDERER_MAP: dict[str, str] = {
    "Property": "PropertyField",
    "MultiLanguageProperty": "MultiLangField",
    "SubmodelElementCollection": "CollectionField",
    "SubmodelElementList": "ListField",
    "Entity": "EntityField",
    "Range": "RangeField",
    "File": "FileField",
    "Blob": "ReadOnlyField",
    "ReferenceElement": "ReferenceField",
    "RelationshipElement": "RelationshipField",
    "AnnotatedRelationshipElement": "AnnotatedRelationshipField",
    "Operation": "ReadOnlyField",
    "Capability": "ReadOnlyField",
    "BasicEventElement": "ReadOnlyField",
}

READONLY_TYPES = {"Blob", "Operation", "Capability", "BasicEventElement"}

CONTAINER_TYPES = {
    "SubmodelElementCollection",
    "SubmodelElementList",
    "Entity",
    "AnnotatedRelationshipElement",
}


# ── Data structures ──────────────────────────────────────────────────────


@dataclass
class ElementRecord:
    path: str
    id_short: str | None
    model_type: str
    depth: int
    has_schema: bool
    schema_type: str | None
    frontend_renderer: str
    is_read_only: bool
    has_children: bool | None  # collections only
    has_items: bool | None  # lists only
    has_statements: bool | None  # entities only
    has_annotations: bool | None  # annotated relationships only
    cardinality: str | None
    semantic_id: str | None


@dataclass
class TemplateAuditResult:
    key: str
    version: str
    total_elements: int = 0
    by_model_type: dict[str, int] = field(default_factory=dict)
    editable_count: int = 0
    readonly_count: int = 0
    editable_coverage_pct: float = 0.0
    empty_lists: int = 0
    childless_collections: int = 0
    statementless_entities: int = 0
    annotationless_relationships: int = 0
    elements: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    qualifier_types_seen: list[str] = field(default_factory=list)
    concept_description_count: int = 0


# ── AST walking ──────────────────────────────────────────────────────────


def walk_definition_ast(
    node: dict[str, Any],
    schema_properties: dict[str, Any] | None,
    depth: int = 0,
    *,
    inherited_schema: dict[str, Any] | None = None,
) -> list[ElementRecord]:
    """Recursively walk a definition node and produce element records.

    Args:
        node: Definition AST node.
        schema_properties: The ``properties`` dict to look up ``idShort`` in.
        depth: Current nesting depth.
        inherited_schema: For anonymous list items, the schema is passed
            directly (from the parent list's ``items``) rather than looked
            up by ``idShort``.
    """
    records: list[ElementRecord] = []

    model_type = node.get("modelType", "")
    id_short = node.get("idShort")
    path = node.get("path", "")

    # Determine schema presence — either looked up by idShort or inherited
    schema_node: dict[str, Any] | None = inherited_schema
    if schema_node is None and schema_properties is not None and id_short:
        schema_node = schema_properties.get(id_short)
    has_schema = schema_node is not None
    schema_type = schema_node.get("type") if schema_node else None

    # Check readonly from SMT qualifiers or inherent type
    smt = node.get("smt") or {}
    access_mode = (smt.get("access_mode") or "").strip().lower()
    is_smt_readonly = access_mode in {"readonly", "read-only", "read_only"}
    is_type_readonly = model_type in READONLY_TYPES
    x_readonly = (schema_node or {}).get("x-readonly", False)
    is_read_only = is_type_readonly or is_smt_readonly or x_readonly

    # Frontend renderer
    if is_smt_readonly and model_type not in READONLY_TYPES:
        renderer = "ReadOnlyField"
    else:
        renderer = RENDERER_MAP.get(model_type, "PropertyField")

    # Container-specific flags
    has_children: bool | None = None
    has_items: bool | None = None
    has_statements: bool | None = None
    has_annotations: bool | None = None

    if model_type == "SubmodelElementCollection":
        children = node.get("children") or []
        has_children = len(children) > 0
    elif model_type == "SubmodelElementList":
        has_items = node.get("items") is not None
    elif model_type == "Entity":
        statements = node.get("statements") or []
        has_statements = len(statements) > 0
    elif model_type == "AnnotatedRelationshipElement":
        annotations = node.get("annotations") or []
        has_annotations = len(annotations) > 0

    record = ElementRecord(
        path=path,
        id_short=id_short,
        model_type=model_type,
        depth=depth,
        has_schema=has_schema,
        schema_type=schema_type,
        frontend_renderer=renderer,
        is_read_only=is_read_only,
        has_children=has_children,
        has_items=has_items,
        has_statements=has_statements,
        has_annotations=has_annotations,
        cardinality=smt.get("cardinality"),
        semantic_id=node.get("semanticId"),
    )
    records.append(record)

    # Recurse into children
    child_schema_props = _get_child_schema_properties(schema_node, model_type)

    if model_type == "SubmodelElementCollection":
        for child in node.get("children") or []:
            records.extend(walk_definition_ast(child, child_schema_props, depth + 1))

    elif model_type == "SubmodelElementList":
        item = node.get("items")
        if isinstance(item, dict):
            # For lists, the schema's "items" describes the anonymous list item
            item_schema = (schema_node or {}).get("items") if schema_node else None
            item_props = item_schema.get("properties") if isinstance(item_schema, dict) else None
            records.extend(
                walk_definition_ast(
                    item, item_props, depth + 1, inherited_schema=item_schema
                )
            )

    elif model_type == "Entity":
        for stmt in node.get("statements") or []:
            records.extend(walk_definition_ast(stmt, child_schema_props, depth + 1))

    elif model_type == "AnnotatedRelationshipElement":
        for ann in node.get("annotations") or []:
            records.extend(walk_definition_ast(ann, child_schema_props, depth + 1))

    return records


def _get_child_schema_properties(
    schema_node: dict[str, Any] | None,
    model_type: str,
) -> dict[str, Any] | None:
    """Extract the properties dict where children should be looked up."""
    if schema_node is None:
        return None

    if model_type == "SubmodelElementCollection":
        return schema_node.get("properties")

    if model_type == "Entity":
        statements_schema = (schema_node.get("properties") or {}).get("statements")
        if isinstance(statements_schema, dict):
            return statements_schema.get("properties")
        return None

    if model_type == "AnnotatedRelationshipElement":
        annotations_schema = (schema_node.get("properties") or {}).get("annotations")
        if isinstance(annotations_schema, dict):
            return annotations_schema.get("properties")
        return None

    return None


# ── Qualifier inventory ──────────────────────────────────────────────────


def collect_qualifier_types(node: dict[str, Any]) -> list[str]:
    """Collect all qualifier type strings used in a definition tree."""
    types: list[str] = []
    for q in node.get("qualifiers") or []:
        qtype = q.get("type")
        if qtype:
            types.append(str(qtype))

    for child in node.get("children") or []:
        types.extend(collect_qualifier_types(child))
    item = node.get("items")
    if isinstance(item, dict):
        types.extend(collect_qualifier_types(item))
    for stmt in node.get("statements") or []:
        types.extend(collect_qualifier_types(stmt))
    for ann in node.get("annotations") or []:
        types.extend(collect_qualifier_types(ann))

    return types


# ── Main audit logic ─────────────────────────────────────────────────────


def audit_template(key: str, version: str) -> TemplateAuditResult | None:
    descriptor = TEMPLATE_CATALOG.get(key)
    if descriptor is None:
        print(f"  SKIP {key}: not in catalog")
        return None

    aas_env = fetch_template_json(descriptor, version)
    if aas_env is None:
        print(f"  FAILED to fetch {key}@{version}")
        return None

    parser = BasyxTemplateParser()
    builder = TemplateDefinitionBuilder()
    converter = DefinitionToSchemaConverter()

    json_bytes = json.dumps(aas_env).encode("utf-8")
    parsed = parser.parse_json(json_bytes, expected_semantic_id=descriptor.semantic_id)

    definition = builder.build_definition(
        template_key=key,
        parsed=parsed,
        idta_version=version,
        semantic_id=descriptor.semantic_id,
    )

    schema = converter.convert(definition)

    # Walk the definition AST against the schema
    submodel_def = definition.get("submodel") or {}
    schema_properties = schema.get("properties") or {}
    elements = submodel_def.get("elements") or []

    all_records: list[ElementRecord] = []
    for element in elements:
        all_records.extend(walk_definition_ast(element, schema_properties, depth=0))

    # Collect qualifier types from the submodel definition
    qualifier_types: list[str] = []
    for q in submodel_def.get("qualifiers") or []:
        qtype = q.get("type")
        if qtype:
            qualifier_types.append(str(qtype))
    for element in elements:
        qualifier_types.extend(collect_qualifier_types(element))

    # Build result
    result = TemplateAuditResult(key=key, version=version)
    result.total_elements = len(all_records)
    result.concept_description_count = len(definition.get("concept_descriptions") or [])

    type_counter: Counter[str] = Counter()
    for rec in all_records:
        type_counter[rec.model_type] += 1
        if rec.is_read_only:
            result.readonly_count += 1
        else:
            result.editable_count += 1

        if rec.model_type == "SubmodelElementList" and rec.has_items is False:
            result.empty_lists += 1
        if rec.model_type == "SubmodelElementCollection" and rec.has_children is False:
            result.childless_collections += 1
        if rec.model_type == "Entity" and rec.has_statements is False:
            result.statementless_entities += 1
        if rec.model_type == "AnnotatedRelationshipElement" and rec.has_annotations is False:
            result.annotationless_relationships += 1

    result.by_model_type = dict(type_counter.most_common())
    result.editable_coverage_pct = (
        round(result.editable_count / result.total_elements * 100, 1)
        if result.total_elements > 0
        else 0.0
    )
    result.elements = [asdict(r) for r in all_records]
    result.qualifier_types_seen = sorted(set(qualifier_types))

    # Identify gaps
    no_schema = [r for r in all_records if not r.has_schema]
    if no_schema:
        for r in no_schema:
            result.gaps.append(
                f"No schema for {r.model_type} at {r.path} (idShort={r.id_short})"
            )

    if result.empty_lists > 0:
        result.gaps.append(
            f"{result.empty_lists} SubmodelElementList(s) with items=None (fallback schema used)"
        )

    if result.childless_collections > 0:
        result.gaps.append(
            f"{result.childless_collections} SubmodelElementCollection(s) with no children"
        )

    if result.statementless_entities > 0:
        result.gaps.append(
            f"{result.statementless_entities} Entity(ies) with no statements"
        )

    if result.annotationless_relationships > 0:
        result.gaps.append(
            f"{result.annotationless_relationships} AnnotatedRelationshipElement(s) "
            "with no annotations"
        )

    # Check for RelationshipElement rendering limitation
    rel_count = type_counter.get("RelationshipElement", 0)
    ann_rel_count = type_counter.get("AnnotatedRelationshipElement", 0)
    if rel_count > 0 or ann_rel_count > 0:
        result.gaps.append(
            f"RelationshipElement first/second rendered as JSON text "
            f"({rel_count} Relationship + {ann_rel_count} AnnotatedRelationship)"
        )

    return result


# ── Output formatting ────────────────────────────────────────────────────


def print_element_tree(records: list[dict[str, Any]]) -> None:
    """Print an indented element tree."""
    for rec in records:
        indent = "  " * (rec["depth"] + 1)
        id_short = rec["id_short"] or "(anonymous)"
        model_type = rec["model_type"]
        renderer = rec["frontend_renderer"]
        schema_flag = "S" if rec["has_schema"] else "!"
        readonly_flag = " [RO]" if rec["is_read_only"] else ""
        cardinality = f" [{rec['cardinality']}]" if rec.get("cardinality") else ""

        extra = ""
        if rec["has_children"] is False:
            extra += " (NO CHILDREN)"
        if rec["has_items"] is False:
            extra += " (NO ITEMS → fallback)"
        if rec["has_statements"] is False:
            extra += " (NO STATEMENTS)"
        if rec["has_annotations"] is False:
            extra += " (NO ANNOTATIONS)"

        print(
            f"{indent}[{schema_flag}] {model_type}: {id_short}"
            f" → {renderer}{readonly_flag}{cardinality}{extra}"
        )


def print_summary(result: TemplateAuditResult) -> None:
    """Print a human-readable summary for one template."""
    print(f"\n{'=' * 60}")
    print(f"  {result.key}@{result.version}")
    print(f"{'=' * 60}")
    print(f"  Total elements: {result.total_elements}")
    print(f"  Concept descriptions: {result.concept_description_count}")

    type_parts = [f"{t}={c}" for t, c in sorted(result.by_model_type.items())]
    print(f"  By type: {', '.join(type_parts)}")

    print(
        f"  Editable: {result.editable_count}/{result.total_elements} "
        f"({result.editable_coverage_pct}%)"
    )
    print(f"  ReadOnly: {result.readonly_count}")
    print(f"  Empty lists (items=None): {result.empty_lists}")
    print(f"  Childless collections: {result.childless_collections}")
    print(f"  Statement-less entities: {result.statementless_entities}")
    print(f"  Annotation-less relationships: {result.annotationless_relationships}")

    if result.qualifier_types_seen:
        print(f"  Qualifier types seen: {', '.join(result.qualifier_types_seen)}")

    print()
    print("  Element tree:")
    print_element_tree(result.elements)

    if result.gaps:
        print()
        print("  Gaps identified:")
        for gap in result.gaps:
            print(f"    - {gap}")
    else:
        print()
        print("  Gaps: None")


# ── Entrypoint ───────────────────────────────────────────────────────────


def main() -> None:
    write_json = "--json" in sys.argv

    # Read golden files to get template keys and versions
    golden_files = sorted(GOLDENS_DIR.glob("*.json"))
    if not golden_files:
        print("No golden files found. Run compute_golden_hashes.py first.")
        sys.exit(1)

    all_results: list[TemplateAuditResult] = []

    for golden_path in golden_files:
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        key = golden["key"]
        version = golden["idta_version"]

        print(f"\nFetching {key}@{version}...")
        result = audit_template(key, version)
        if result is not None:
            all_results.append(result)
            print_summary(result)

    # Grand summary
    print(f"\n{'=' * 60}")
    print("  GRAND SUMMARY")
    print(f"{'=' * 60}")
    total_elements = sum(r.total_elements for r in all_results)
    total_editable = sum(r.editable_count for r in all_results)
    total_readonly = sum(r.readonly_count for r in all_results)
    total_gaps = sum(len(r.gaps) for r in all_results)
    overall_pct = (
        round(total_editable / total_elements * 100, 1) if total_elements > 0 else 0.0
    )

    print(f"  Templates audited: {len(all_results)}")
    print(f"  Total elements: {total_elements}")
    print(f"  Total editable: {total_editable} ({overall_pct}%)")
    print(f"  Total readonly: {total_readonly}")
    print(f"  Total gaps: {total_gaps}")

    # Aggregate type counts
    agg_types: Counter[str] = Counter()
    for r in all_results:
        for t, c in r.by_model_type.items():
            agg_types[t] += c
    type_parts = [f"{t}={c}" for t, c in agg_types.most_common()]
    print(f"  Aggregate by type: {', '.join(type_parts)}")

    # All unique qualifier types
    all_qual_types = set()
    for r in all_results:
        all_qual_types.update(r.qualifier_types_seen)
    if all_qual_types:
        print(f"  All qualifier types: {', '.join(sorted(all_qual_types))}")

    # No-schema elements across all templates
    no_schema_total = sum(
        1
        for r in all_results
        for e in r.elements
        if not e["has_schema"]
    )
    if no_schema_total > 0:
        print(f"  WARNING: {no_schema_total} element(s) have no JSON Schema coverage")

    if write_json:
        report = {
            "summary": {
                "templates_audited": len(all_results),
                "total_elements": total_elements,
                "total_editable": total_editable,
                "total_readonly": total_readonly,
                "overall_editable_pct": overall_pct,
                "total_gaps": total_gaps,
                "aggregate_by_type": dict(agg_types.most_common()),
                "all_qualifier_types": sorted(all_qual_types),
            },
            "templates": [asdict(r) for r in all_results],
        }
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\n  Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
