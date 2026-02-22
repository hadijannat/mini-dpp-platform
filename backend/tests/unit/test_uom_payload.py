from __future__ import annotations

from app.modules.units.constants import DATA_SPECIFICATION_UOM_TEMPLATE_ID
from app.modules.units.payload import (
    collect_unit_ids_from_iec61360,
    collect_uom_by_cd_id,
    strip_uom_data_specifications,
)


def _sample_environment() -> dict[str, object]:
    return {
        "assetAdministrationShells": [],
        "submodels": [],
        "conceptDescriptions": [
            {
                "id": "urn:unece:rec20:MTR",
                "idShort": "UnitMTR",
                "embeddedDataSpecifications": [
                    {
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
                            "modelType": "DataSpecificationUoM",
                            "preferredName": [{"language": "en", "text": "metre"}],
                            "symbol": "m",
                            "specificUnitID": "MTR",
                            "definition": [{"language": "en", "text": "SI unit for length"}],
                            "preferredNameQuantity": [{"language": "en", "text": "length"}],
                            "quantityID": "LEN",
                            "classificationSystem": "UNECE Rec 20",
                        },
                    }
                ],
            },
            {
                "id": "urn:example:Length",
                "idShort": "Length",
                "embeddedDataSpecifications": [
                    {
                        "dataSpecificationContent": {
                            "modelType": "DataSpecificationIEC61360",
                            "dataType": "REAL_MEASURE",
                            "unit": "m",
                            "unitId": {
                                "type": "ExternalReference",
                                "keys": [{"type": "ConceptDescription", "value": "urn:unece:rec20:MTR"}],
                            },
                        }
                    }
                ],
            },
        ],
    }


def test_collect_uom_by_cd_id_extracts_structured_payload() -> None:
    result = collect_uom_by_cd_id(_sample_environment())

    assert "urn:unece:rec20:MTR" in result
    assert result["urn:unece:rec20:MTR"].symbol == "m"
    assert result["urn:unece:rec20:MTR"].specific_unit_id == "MTR"


def test_strip_uom_data_specifications_keeps_other_specs() -> None:
    stripped, stats = strip_uom_data_specifications(_sample_environment())
    concept_descriptions = stripped["conceptDescriptions"]
    assert isinstance(concept_descriptions, list)
    assert stats["uom_specs_removed"] == 1
    assert stats["concept_descriptions_scanned"] == 2

    unit_cd = next(cd for cd in concept_descriptions if cd.get("id") == "urn:unece:rec20:MTR")
    assert unit_cd.get("embeddedDataSpecifications") == []

    property_cd = next(cd for cd in concept_descriptions if cd.get("id") == "urn:example:Length")
    embedded = property_cd.get("embeddedDataSpecifications")
    assert isinstance(embedded, list)
    assert len(embedded) == 1


def test_collect_unit_ids_from_iec61360_reads_reference_values() -> None:
    unit_ids = collect_unit_ids_from_iec61360(_sample_environment())
    assert unit_ids == {"urn:unece:rec20:MTR"}
