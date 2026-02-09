"""Template conformance diagnostics and report generator."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.db import session as db_session
from app.db.models import Template
from app.db.session import init_db
from app.modules.templates.basyx_parser import BasyxTemplateParser
from app.modules.templates.catalog import get_template_descriptor, list_template_keys
from app.modules.templates.definition import TemplateDefinitionBuilder
from app.modules.templates.qualifiers import (
    ACCESS_MODE_SEMANTIC_IDS,
    ALLOWED_ID_SHORT_SEMANTIC_IDS,
    ALLOWED_RANGE_SEMANTIC_IDS,
    ALLOWED_VALUE_SEMANTIC_IDS,
    CARDINALITY_SEMANTIC_IDS,
    DEFAULT_VALUE_SEMANTIC_IDS,
    EDIT_ID_SHORT_SEMANTIC_IDS,
    EITHER_OR_SEMANTIC_IDS,
    EXAMPLE_VALUE_SEMANTIC_IDS,
    FORM_CHOICES_SEMANTIC_IDS,
    FORM_INFO_SEMANTIC_IDS,
    FORM_TITLE_SEMANTIC_IDS,
    FORM_URL_SEMANTIC_IDS,
    INITIAL_VALUE_SEMANTIC_IDS,
    NAMING_SEMANTIC_IDS,
    REQUIRED_LANG_SEMANTIC_IDS,
)

SUPPORTED_QUALIFIER_TYPES = {
    "SMT/Cardinality",
    "Cardinality",
    "SMT/Multiplicity",
    "Multiplicity",
    "SMT/EitherOr",
    "EitherOr",
    "SMT/DefaultValue",
    "DefaultValue",
    "SMT/InitialValue",
    "InitialValue",
    "SMT/ExampleValue",
    "ExampleValue",
    "SMT/AllowedRange",
    "AllowedRange",
    "SMT/AllowedValue",
    "AllowedValue",
    "SMT/RequiredLang",
    "RequiredLang",
    "SMT/AccessMode",
    "AccessMode",
    "SMT/FormTitle",
    "FormTitle",
    "SMT/FormInfo",
    "FormInfo",
    "SMT/FormUrl",
    "FormUrl",
    "SMT/FormChoices",
    "FormChoices",
    "SMT/Naming",
    "Naming",
    "SMT/AllowedIdShort",
    "AllowedIdShort",
    "SMT/EditIdShort",
    "EditIdShort",
}

SUPPORTED_QUALIFIER_SEMANTIC_IDS = (
    CARDINALITY_SEMANTIC_IDS
    | EITHER_OR_SEMANTIC_IDS
    | DEFAULT_VALUE_SEMANTIC_IDS
    | INITIAL_VALUE_SEMANTIC_IDS
    | EXAMPLE_VALUE_SEMANTIC_IDS
    | ALLOWED_RANGE_SEMANTIC_IDS
    | ALLOWED_VALUE_SEMANTIC_IDS
    | REQUIRED_LANG_SEMANTIC_IDS
    | ACCESS_MODE_SEMANTIC_IDS
    | FORM_TITLE_SEMANTIC_IDS
    | FORM_INFO_SEMANTIC_IDS
    | FORM_URL_SEMANTIC_IDS
    | FORM_CHOICES_SEMANTIC_IDS
    | NAMING_SEMANTIC_IDS
    | ALLOWED_ID_SHORT_SEMANTIC_IDS
    | EDIT_ID_SHORT_SEMANTIC_IDS
)


def _iter_definition_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node]
    for child in node.get("children", []) or []:
        nodes.extend(_iter_definition_nodes(child))
    if node.get("items"):
        nodes.extend(_iter_definition_nodes(node["items"]))
    for child in node.get("statements", []) or []:
        nodes.extend(_iter_definition_nodes(child))
    for child in node.get("annotations", []) or []:
        nodes.extend(_iter_definition_nodes(child))
    return nodes


def _collect_definition_nodes(definition: dict[str, Any]) -> list[dict[str, Any]]:
    submodel = definition.get("submodel", {})
    nodes: list[dict[str, Any]] = []
    for element in submodel.get("elements", []) or []:
        nodes.extend(_iter_definition_nodes(element))
    return nodes


def _schema_has_path(schema: dict[str, Any], path: str, root_id_short: str | None) -> bool:
    if not schema:
        return False
    parts = [part for part in path.split("/") if part]
    if root_id_short and parts and parts[0] == root_id_short:
        parts = parts[1:]
    steps: list[str] = []
    for part in parts:
        if part.endswith("[]"):
            steps.append(part[:-2])
            steps.append("[]")
        else:
            steps.append(part)

    current: dict[str, Any] | None = schema
    for step in steps:
        if current is None:
            return False
        if step == "[]":
            current = current.get("items") if isinstance(current, dict) else None
            continue
        if current.get("type") == "array":
            current = current.get("items")
        if not current or current.get("type") != "object":
            return False
        current = (current.get("properties") or {}).get(step)
    return current is not None


def _collect_qualifiers(definition: dict[str, Any]) -> list[dict[str, Any]]:
    qualifiers: list[dict[str, Any]] = []
    submodel = definition.get("submodel", {})
    qualifiers.extend(submodel.get("qualifiers", []) or [])
    for node in _collect_definition_nodes(definition):
        qualifiers.extend(node.get("qualifiers", []) or [])
    return qualifiers


def find_schema_missing_paths(definition: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    submodel = definition.get("submodel", {})
    root_id_short = submodel.get("idShort")
    nodes = _collect_definition_nodes(definition)
    missing_paths: list[str] = []
    for node in nodes:
        path = node.get("path")
        if not path:
            continue
        if not _schema_has_path(schema, path, root_id_short):
            missing_paths.append(path)
    return missing_paths


async def build_conformance_report() -> dict[str, Any]:
    await init_db()
    report: dict[str, Any] = {
        "templates": [],
    }

    session_factory = db_session._session_factory
    if session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with session_factory() as session:
        result = await session.execute(select(Template).order_by(Template.template_key))
        templates = result.scalars().all()
        templates_by_key = {template.template_key: template for template in templates}

        parser = BasyxTemplateParser()
        builder = TemplateDefinitionBuilder()

        for template_key in list_template_keys(refreshable_only=True):
            descriptor = get_template_descriptor(template_key)
            template = templates_by_key.get(template_key)
            template_report: dict[str, Any] = {
                "template_key": template_key,
                "status": "ok",
                "errors": [],
            }

            if descriptor is None:
                template_report["status"] = "error"
                template_report["errors"].append("missing_descriptor")
                report["templates"].append(template_report)
                continue

            if template is None:
                template_report["status"] = "error"
                template_report["errors"].append("missing_template")
                report["templates"].append(template_report)
                continue

            template_report["idta_version"] = template.idta_version
            template_report["source_url"] = template.source_url

            parsed = None
            if template.template_aasx:
                try:
                    parsed = parser.parse_aasx(
                        template.template_aasx,
                        expected_semantic_id=descriptor.semantic_id,
                    )
                except Exception as exc:  # pragma: no cover - diagnostic
                    template_report["errors"].append(f"aasx_parse_failed:{exc}")

            if parsed is None:
                try:
                    payload = json.dumps(template.template_json).encode()
                    parsed = parser.parse_json(payload, expected_semantic_id=descriptor.semantic_id)
                except Exception as exc:  # pragma: no cover - diagnostic
                    template_report["status"] = "error"
                    template_report["errors"].append(f"json_parse_failed:{exc}")
                    report["templates"].append(template_report)
                    continue

            definition = builder.build_definition(
                template_key=template_key,
                parsed=parsed,
                idta_version=template.idta_version,
                semantic_id=template.semantic_id,
            )

            submodel = definition.get("submodel", {})
            root_id_short = submodel.get("idShort")
            nodes = _collect_definition_nodes(definition)

            template_report["submodel_id_short"] = root_id_short
            template_report["element_count"] = len(nodes)

            qualifiers = _collect_qualifiers(definition)
            qualifier_types = Counter(
                str(q.get("type", "")).strip() for q in qualifiers if q.get("type") is not None
            )
            qualifier_semantic_ids: Counter[str] = Counter()
            for qualifier in qualifiers:
                sem = qualifier.get("semanticId")
                if not isinstance(sem, dict):
                    continue
                keys = sem.get("keys") or []
                if not keys:
                    continue
                value = keys[0].get("value")
                if value:
                    qualifier_semantic_ids[str(value)] += 1

            unsupported = []
            for qualifier in qualifiers:
                qtype = str(qualifier.get("type", "")).strip()
                semantic_id = None
                sem = qualifier.get("semanticId")
                if isinstance(sem, dict):
                    keys = sem.get("keys") or []
                    if keys:
                        semantic_id = str(keys[0].get("value"))

                if (qtype and qtype in SUPPORTED_QUALIFIER_TYPES) or (
                    semantic_id and semantic_id in SUPPORTED_QUALIFIER_SEMANTIC_IDS
                ):
                    continue
                unsupported.append(qtype or semantic_id or "unknown")

            template_report["qualifiers_total"] = len(qualifiers)
            template_report["qualifiers_supported"] = len(qualifiers) - len(unsupported)
            template_report["qualifiers_unsupported"] = sorted(set(unsupported))
            template_report["qualifier_types_seen"] = dict(qualifier_types)
            template_report["qualifier_semantic_ids_seen"] = dict(qualifier_semantic_ids)

            # UI schema coverage check
            from app.modules.templates.service import TemplateRegistryService

            ui_schema = TemplateRegistryService(session).generate_ui_schema(template)
            missing_paths = find_schema_missing_paths(definition, ui_schema)

            template_report["schema_missing_paths"] = missing_paths[:25]
            template_report["schema_missing_count"] = len(missing_paths)

            report["templates"].append(template_report)

    return report


async def _run() -> None:
    report = await build_conformance_report()
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate template conformance report.")
    parser.parse_args()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
