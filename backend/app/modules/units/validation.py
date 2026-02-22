"""Validation and diagnostics for IEC61360 unit linkage and UoM resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.units.models import UomDataSpecification, UomRegistryEntry


@dataclass(frozen=True)
class ResolvedUnit:
    data_specification: UomDataSpecification | None
    source: str | None
    warnings: list[str]


def is_measure_or_currency_datatype(data_type: str | None) -> bool:
    if not data_type:
        return False
    upper = data_type.strip().upper()
    if not upper:
        return False
    return upper.endswith("_MEASURE") or upper.endswith("_CURRENCY")


def resolve_uom_for_unit_reference(
    *,
    unit_reference: str,
    template_uom_by_cd_id: dict[str, UomDataSpecification],
    registry_by_cd_id: dict[str, UomRegistryEntry],
    registry_by_specific_unit_id: dict[str, list[UomRegistryEntry]],
    registry_by_symbol: dict[str, list[UomRegistryEntry]],
) -> ResolvedUnit:
    unit_reference_normalized = unit_reference.strip()
    if not unit_reference_normalized:
        return ResolvedUnit(data_specification=None, source=None, warnings=[])

    template_match = template_uom_by_cd_id.get(unit_reference_normalized)
    if template_match is not None:
        return ResolvedUnit(
            data_specification=template_match,
            source="template_raw",
            warnings=[],
        )

    registry_cd = registry_by_cd_id.get(unit_reference_normalized)
    if registry_cd is not None:
        return ResolvedUnit(
            data_specification=registry_cd.data_specification,
            source="registry_cd_id",
            warnings=[],
        )

    specific_matches = registry_by_specific_unit_id.get(unit_reference_normalized, [])
    if len(specific_matches) == 1:
        return ResolvedUnit(
            data_specification=specific_matches[0].data_specification,
            source="registry_specific_unit_id",
            warnings=[],
        )
    if len(specific_matches) > 1:
        return ResolvedUnit(
            data_specification=None,
            source=None,
            warnings=["ambiguous_specific_unit_id"],
        )

    symbol_matches = registry_by_symbol.get(unit_reference_normalized, [])
    if len(symbol_matches) == 1:
        return ResolvedUnit(
            data_specification=symbol_matches[0].data_specification,
            source="registry_symbol",
            warnings=[],
        )
    if len(symbol_matches) > 1:
        return ResolvedUnit(
            data_specification=None,
            source=None,
            warnings=["ambiguous_symbol_match"],
        )

    return ResolvedUnit(data_specification=None, source=None, warnings=["unresolved_unit_reference"])


def build_uom_diagnostics(
    *,
    concept_descriptions: list[dict[str, Any]],
    template_uom_by_cd_id: dict[str, UomDataSpecification],
    registry_by_cd_id: dict[str, UomRegistryEntry],
    registry_by_specific_unit_id: dict[str, list[UomRegistryEntry]],
    registry_by_symbol: dict[str, list[UomRegistryEntry]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    by_cd_id: dict[str, list[dict[str, Any]]] = {}

    cd_index: dict[str, dict[str, Any]] = {}
    for cd in concept_descriptions:
        cd_id = str(cd.get("id") or "").strip()
        if cd_id:
            cd_index[cd_id] = cd

    measure_count = 0
    with_unit_or_unit_id = 0
    resolved_unit_links = 0

    for cd in concept_descriptions:
        cd_id = str(cd.get("id") or "").strip()
        data_type = _to_optional_str(cd.get("dataType"))
        unit = _to_optional_str(cd.get("unit"))
        unit_id = _to_optional_str(cd.get("unitId"))

        if is_measure_or_currency_datatype(data_type):
            measure_count += 1
            if unit or unit_id:
                with_unit_or_unit_id += 1
            else:
                _add_issue(
                    issues,
                    by_cd_id,
                    {
                        "code": "missing_unit_for_measure",
                        "severity": "warning",
                        "conceptDescriptionId": cd_id,
                        "message": (
                            "IEC61360 measure/currency datatype should define unit and/or unitId."
                        ),
                    },
                )

        if not unit_id:
            continue

        resolved = resolve_uom_for_unit_reference(
            unit_reference=unit_id,
            template_uom_by_cd_id=template_uom_by_cd_id,
            registry_by_cd_id=registry_by_cd_id,
            registry_by_specific_unit_id=registry_by_specific_unit_id,
            registry_by_symbol=registry_by_symbol,
        )

        for warning_code in resolved.warnings:
            _add_issue(
                issues,
                by_cd_id,
                {
                    "code": warning_code,
                    "severity": "warning",
                    "conceptDescriptionId": cd_id,
                    "unitId": unit_id,
                    "message": _warning_message_for_code(warning_code, unit_id=unit_id),
                },
            )

        target_cd = cd_index.get(unit_id)
        target_cd_has_uom = isinstance(target_cd, dict) and isinstance(target_cd.get("uom"), dict)

        if resolved.data_specification is None and not target_cd_has_uom:
            _add_issue(
                issues,
                by_cd_id,
                {
                    "code": "unit_id_target_missing_uom",
                    "severity": "warning",
                    "conceptDescriptionId": cd_id,
                    "unitId": unit_id,
                    "message": (
                        "unitId does not resolve to a ConceptDescription with DataSpecificationUoM."
                    ),
                },
            )
            continue

        resolved_unit_links += 1

        resolved_symbol = resolved.data_specification.symbol if resolved.data_specification else None
        if not resolved_symbol and isinstance(target_cd, dict):
            target_uom = target_cd.get("uom")
            if isinstance(target_uom, dict):
                resolved_symbol = _to_optional_str(target_uom.get("symbol"))

        if unit and resolved_symbol and unit != resolved_symbol:
            _add_issue(
                issues,
                by_cd_id,
                {
                    "code": "unit_symbol_mismatch",
                    "severity": "warning",
                    "conceptDescriptionId": cd_id,
                    "unitId": unit_id,
                    "message": (
                        f"IEC61360 unit '{unit}' does not match resolved UoM symbol "
                        f"'{resolved_symbol}'."
                    ),
                    "resolvedSource": resolved.source,
                },
            )

    return {
        "summary": {
            "concept_descriptions_total": len(concept_descriptions),
            "measure_or_currency_total": measure_count,
            "measure_or_currency_with_unit_or_unit_id": with_unit_or_unit_id,
            "unit_links_resolved": resolved_unit_links,
            "warnings_total": len(issues),
        },
        "issues": issues,
        "by_concept_description_id": by_cd_id,
    }


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _add_issue(
    issues: list[dict[str, Any]],
    by_cd_id: dict[str, list[dict[str, Any]]],
    issue: dict[str, Any],
) -> None:
    issues.append(issue)
    cd_id = str(issue.get("conceptDescriptionId") or "").strip()
    if not cd_id:
        return
    by_cd_id.setdefault(cd_id, []).append(issue)


def _warning_message_for_code(code: str, *, unit_id: str) -> str:
    if code == "ambiguous_specific_unit_id":
        return f"specificUnitID '{unit_id}' maps to multiple registry units."
    if code == "ambiguous_symbol_match":
        return f"Unit symbol '{unit_id}' maps to multiple registry units."
    return f"Could not resolve unit reference '{unit_id}'."
