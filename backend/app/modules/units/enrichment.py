"""Export-time UoM ConceptDescription enrichment."""

from __future__ import annotations

from typing import Any

from app.modules.units.constants import (
    DATA_SPECIFICATION_UOM_MODEL_TYPE,
    DATA_SPECIFICATION_UOM_TEMPLATE_ID,
)
from app.modules.units.models import UomDataSpecification, UomRegistryEntry
from app.modules.units.payload import (
    collect_unit_ids_from_iec61360,
    copy_payload,
    extract_uom_content_from_concept_description,
)
from app.modules.units.validation import resolve_uom_for_unit_reference


def ensure_uom_concept_descriptions(
    *,
    aas_env: dict[str, Any],
    template_uom_by_cd_id: dict[str, UomDataSpecification],
    registry_by_cd_id: dict[str, UomRegistryEntry],
    registry_by_specific_unit_id: dict[str, list[UomRegistryEntry]],
    registry_by_symbol: dict[str, list[UomRegistryEntry]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ensure unit references point to ConceptDescriptions with DataSpecificationUoM."""
    enriched = copy_payload(aas_env)
    concept_descriptions = enriched.setdefault("conceptDescriptions", [])
    if not isinstance(concept_descriptions, list):
        concept_descriptions = []
        enriched["conceptDescriptions"] = concept_descriptions

    by_cd_id: dict[str, dict[str, Any]] = {}
    for concept_description in concept_descriptions:
        if not isinstance(concept_description, dict):
            continue
        cd_id = str(concept_description.get("id") or "").strip()
        if cd_id:
            by_cd_id[cd_id] = concept_description

    referenced_unit_ids = sorted(collect_unit_ids_from_iec61360(enriched))
    inserted = 0
    repaired = 0
    missing_refs: list[str] = []

    for unit_id in referenced_unit_ids:
        existing = by_cd_id.get(unit_id)
        if (
            existing is not None
            and extract_uom_content_from_concept_description(existing) is not None
        ):
            continue

        resolved = resolve_uom_for_unit_reference(
            unit_reference=unit_id,
            template_uom_by_cd_id=template_uom_by_cd_id,
            registry_by_cd_id=registry_by_cd_id,
            registry_by_specific_unit_id=registry_by_specific_unit_id,
            registry_by_symbol=registry_by_symbol,
        )
        if resolved.data_specification is None:
            missing_refs.append(unit_id)
            continue

        if existing is None:
            new_cd = build_uom_concept_description(
                cd_id=unit_id,
                data_specification=resolved.data_specification,
            )
            concept_descriptions.append(new_cd)
            by_cd_id[unit_id] = new_cd
            inserted += 1
            continue

        attach_uom_to_concept_description(existing, resolved.data_specification)
        repaired += 1

    concept_descriptions.sort(key=_concept_description_sort_key)

    return enriched, {
        "referenced_unit_ids": len(referenced_unit_ids),
        "inserted_unit_concept_descriptions": inserted,
        "repaired_unit_concept_descriptions": repaired,
        "missing_unit_references": sorted(set(missing_refs)),
    }


def attach_uom_to_concept_description(
    concept_description: dict[str, Any],
    data_specification: UomDataSpecification,
) -> None:
    embedded = concept_description.get("embeddedDataSpecifications")
    if not isinstance(embedded, list):
        embedded = []
        concept_description["embeddedDataSpecifications"] = embedded

    for entry in embedded:
        if not isinstance(entry, dict):
            continue
        content = entry.get("dataSpecificationContent")
        if (
            isinstance(content, dict)
            and str(content.get("modelType")) == DATA_SPECIFICATION_UOM_MODEL_TYPE
        ):
            return

    embedded.append(build_uom_embedded_data_specification(data_specification))


def build_uom_concept_description(
    *,
    cd_id: str,
    data_specification: UomDataSpecification,
) -> dict[str, Any]:
    id_short = _build_id_short_from_symbol(data_specification.symbol)
    concept_description = {
        "modelType": "ConceptDescription",
        "id": cd_id,
        "idShort": id_short,
        "embeddedDataSpecifications": [
            build_uom_embedded_data_specification(data_specification),
        ],
    }
    if data_specification.definition:
        concept_description["description"] = [
            {"language": language, "text": text}
            for language, text in sorted(data_specification.definition.items())
        ]
    return concept_description


def build_uom_embedded_data_specification(
    data_specification: UomDataSpecification,
) -> dict[str, Any]:
    return {
        "dataSpecification": {
            "type": "ExternalReference",
            "keys": [
                {
                    "type": "GlobalReference",
                    "value": DATA_SPECIFICATION_UOM_TEMPLATE_ID,
                }
            ],
        },
        "dataSpecificationContent": {
            "modelType": DATA_SPECIFICATION_UOM_MODEL_TYPE,
            **data_specification.to_payload(),
        },
    }


def _build_id_short_from_symbol(symbol: str) -> str:
    cleaned = "".join(char for char in symbol if char.isalnum())
    if cleaned:
        return f"Unit{cleaned[:64]}"
    return "Unit"


def _concept_description_sort_key(concept_description: Any) -> tuple[str, str]:
    if not isinstance(concept_description, dict):
        return ("", "")
    return (
        str(concept_description.get("id") or ""),
        str(concept_description.get("idShort") or ""),
    )
