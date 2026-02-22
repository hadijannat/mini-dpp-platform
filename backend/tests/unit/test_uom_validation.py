from __future__ import annotations

from app.modules.units.models import UomDataSpecification, UomRegistryEntry
from app.modules.units.validation import build_uom_diagnostics, resolve_uom_for_unit_reference


def _uom(symbol: str, specific_unit_id: str) -> UomDataSpecification:
    return UomDataSpecification(
        preferred_name={"en": "unit"},
        symbol=symbol,
        specific_unit_id=specific_unit_id,
        definition={"en": "definition"},
        preferred_name_quantity={"en": "quantity"},
        quantity_id="QTY",
        classification_system="UNECE Rec 20",
        classification_system_version="2024",
    )


def test_resolve_uom_precedence_template_then_registry() -> None:
    template_match = _uom("m", "MTR")
    registry_entry = UomRegistryEntry(cd_id="urn:unit:m", data_specification=_uom("meter", "MTR"))

    resolved = resolve_uom_for_unit_reference(
        unit_reference="urn:unit:m",
        template_uom_by_cd_id={"urn:unit:m": template_match},
        registry_by_cd_id={"urn:unit:m": registry_entry},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )
    assert resolved.data_specification is not None
    assert resolved.data_specification.symbol == "m"
    assert resolved.source == "template_raw"

    resolved_registry = resolve_uom_for_unit_reference(
        unit_reference="urn:unit:m",
        template_uom_by_cd_id={},
        registry_by_cd_id={"urn:unit:m": registry_entry},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )
    assert resolved_registry.data_specification is not None
    assert resolved_registry.data_specification.symbol == "meter"
    assert resolved_registry.source == "registry_cd_id"


def test_build_uom_diagnostics_warns_on_missing_and_mismatch() -> None:
    registry_entry = UomRegistryEntry(cd_id="urn:unit:m", data_specification=_uom("m", "MTR"))
    concept_descriptions = [
        {
            "id": "urn:cd:length",
            "dataType": "REAL_MEASURE",
            "unit": "kg",
            "unitId": "urn:unit:m",
        },
        {
            "id": "urn:cd:temperature",
            "dataType": "REAL_MEASURE",
        },
    ]

    diagnostics = build_uom_diagnostics(
        concept_descriptions=concept_descriptions,
        template_uom_by_cd_id={},
        registry_by_cd_id={"urn:unit:m": registry_entry},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )

    summary = diagnostics["summary"]
    assert summary["measure_or_currency_total"] == 2
    assert summary["measure_or_currency_with_unit_or_unit_id"] == 1
    assert summary["unit_links_resolved"] == 1

    issue_codes = {issue["code"] for issue in diagnostics["issues"]}
    assert "missing_unit_for_measure" in issue_codes
    assert "unit_symbol_mismatch" in issue_codes
