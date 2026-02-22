from __future__ import annotations

from app.modules.units.constants import DATA_SPECIFICATION_UOM_TEMPLATE_ID
from app.modules.units.enrichment import ensure_uom_concept_descriptions
from app.modules.units.models import UomDataSpecification


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


def _aas_env_with_measure_unit_reference() -> dict[str, object]:
    return {
        "assetAdministrationShells": [],
        "submodels": [],
        "conceptDescriptions": [
            {
                "id": "urn:cd:length",
                "embeddedDataSpecifications": [
                    {
                        "dataSpecificationContent": {
                            "modelType": "DataSpecificationIEC61360",
                            "dataType": "REAL_MEASURE",
                            "unit": "m",
                            "unitId": {
                                "type": "ExternalReference",
                                "keys": [
                                    {"type": "ConceptDescription", "value": "urn:unit:m"},
                                ],
                            },
                        }
                    }
                ],
            }
        ],
    }


def test_uom_enrichment_injects_missing_unit_concept_descriptions() -> None:
    enriched, stats = ensure_uom_concept_descriptions(
        aas_env=_aas_env_with_measure_unit_reference(),
        template_uom_by_cd_id={"urn:unit:m": _uom("m", "MTR")},
        registry_by_cd_id={},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )

    assert stats["inserted_unit_concept_descriptions"] == 1
    concept_descriptions = enriched["conceptDescriptions"]
    assert isinstance(concept_descriptions, list)
    unit_cd = next(cd for cd in concept_descriptions if cd.get("id") == "urn:unit:m")
    embedded = unit_cd["embeddedDataSpecifications"][0]
    assert embedded["dataSpecification"]["keys"][0]["value"] == DATA_SPECIFICATION_UOM_TEMPLATE_ID


def test_uom_enrichment_is_idempotent() -> None:
    first, _ = ensure_uom_concept_descriptions(
        aas_env=_aas_env_with_measure_unit_reference(),
        template_uom_by_cd_id={"urn:unit:m": _uom("m", "MTR")},
        registry_by_cd_id={},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )
    second, stats = ensure_uom_concept_descriptions(
        aas_env=first,
        template_uom_by_cd_id={"urn:unit:m": _uom("m", "MTR")},
        registry_by_cd_id={},
        registry_by_specific_unit_id={},
        registry_by_symbol={},
    )

    concept_descriptions = second["conceptDescriptions"]
    assert isinstance(concept_descriptions, list)
    assert len([cd for cd in concept_descriptions if cd.get("id") == "urn:unit:m"]) == 1
    assert stats["inserted_unit_concept_descriptions"] == 0
