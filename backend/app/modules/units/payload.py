"""Helpers for reading and mutating UoM-related data in AAS JSON payloads."""

from __future__ import annotations

import json
from typing import Any, cast

from app.modules.units.constants import (
    DATA_SPECIFICATION_IEC61360_MODEL_TYPE,
    DATA_SPECIFICATION_UOM_MODEL_TYPE,
    DATA_SPECIFICATION_UOM_TEMPLATE_ID,
)
from app.modules.units.models import UomDataSpecification


def copy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy a JSON payload with deterministic semantics."""
    return cast(dict[str, Any], json.loads(json.dumps(payload, ensure_ascii=False)))


def model_type_name(payload: Any) -> str | None:
    if isinstance(payload, dict):
        raw = payload.get("modelType")
        if isinstance(raw, dict):
            name = raw.get("name")
            if name is not None:
                return str(name)
        if raw is not None:
            return str(raw)
    if isinstance(payload, str):
        return payload
    return None


def reference_key_values(reference: Any) -> list[str]:
    if not isinstance(reference, dict):
        return []
    keys = reference.get("keys")
    if not isinstance(keys, list):
        return []
    values: list[str] = []
    for key in keys:
        if not isinstance(key, dict):
            continue
        raw = key.get("value")
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            values.append(value)
    return values


def extract_uom_content_from_concept_description(
    concept_description: dict[str, Any],
) -> UomDataSpecification | None:
    for embedded in _embedded_data_specifications(concept_description):
        if not _is_uom_data_specification(embedded):
            continue
        content = embedded.get("dataSpecificationContent")
        if not isinstance(content, dict):
            continue
        parsed = UomDataSpecification.from_payload(content)
        if parsed is not None:
            return parsed
    return None


def extract_iec61360_content_from_concept_description(
    concept_description: dict[str, Any],
) -> dict[str, Any] | None:
    for embedded in _embedded_data_specifications(concept_description):
        content = embedded.get("dataSpecificationContent")
        if not isinstance(content, dict):
            continue
        if model_type_name(content) != DATA_SPECIFICATION_IEC61360_MODEL_TYPE:
            continue
        return content
    return None


def extract_unit_id_from_iec61360(content: dict[str, Any]) -> str | None:
    unit_id = content.get("unitId")
    if isinstance(unit_id, dict):
        values = reference_key_values(unit_id)
        if values:
            return values[0]
    return None


def collect_uom_by_cd_id(payload: dict[str, Any]) -> dict[str, UomDataSpecification]:
    concept_descriptions = payload.get("conceptDescriptions")
    if not isinstance(concept_descriptions, list):
        return {}

    result: dict[str, UomDataSpecification] = {}
    for concept_description in concept_descriptions:
        if not isinstance(concept_description, dict):
            continue
        cd_id = str(concept_description.get("id") or "").strip()
        if not cd_id:
            continue
        uom = extract_uom_content_from_concept_description(concept_description)
        if uom is None:
            continue
        result[cd_id] = uom
    return dict(sorted(result.items(), key=lambda pair: pair[0]))


def strip_uom_data_specifications(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Remove DataSpecificationUoM blocks while preserving CD identities and other specs."""
    sanitized = copy_payload(payload)
    concept_descriptions = sanitized.get("conceptDescriptions")
    if not isinstance(concept_descriptions, list):
        return sanitized, {"concept_descriptions_scanned": 0, "uom_specs_removed": 0}

    scanned = 0
    removed = 0
    for concept_description in concept_descriptions:
        if not isinstance(concept_description, dict):
            continue
        scanned += 1
        embedded = concept_description.get("embeddedDataSpecifications")
        if not isinstance(embedded, list) or not embedded:
            continue
        kept: list[Any] = []
        for entry in embedded:
            if not isinstance(entry, dict):
                kept.append(entry)
                continue
            if _is_uom_data_specification(entry):
                removed += 1
                continue
            kept.append(entry)
        concept_description["embeddedDataSpecifications"] = kept

    return sanitized, {
        "concept_descriptions_scanned": scanned,
        "uom_specs_removed": removed,
    }


def collect_unit_ids_from_iec61360(payload: dict[str, Any]) -> set[str]:
    concept_descriptions = payload.get("conceptDescriptions")
    if not isinstance(concept_descriptions, list):
        return set()

    unit_ids: set[str] = set()
    for concept_description in concept_descriptions:
        if not isinstance(concept_description, dict):
            continue
        iec = extract_iec61360_content_from_concept_description(concept_description)
        if iec is None:
            continue
        unit_id = extract_unit_id_from_iec61360(iec)
        if unit_id:
            unit_ids.add(unit_id)
    return unit_ids


def _embedded_data_specifications(concept_description: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = concept_description.get("embeddedDataSpecifications")
    if not isinstance(embedded, list):
        return []
    return [entry for entry in embedded if isinstance(entry, dict)]


def _is_uom_data_specification(embedded: dict[str, Any]) -> bool:
    content = embedded.get("dataSpecificationContent")
    if isinstance(content, dict) and model_type_name(content) == DATA_SPECIFICATION_UOM_MODEL_TYPE:
        return True

    specification_ref = embedded.get("dataSpecification")
    key_values = reference_key_values(specification_ref)
    return DATA_SPECIFICATION_UOM_TEMPLATE_ID in key_values
