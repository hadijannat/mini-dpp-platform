"""Unit tests for TemplateDefinitionBuilder concept-description decoration."""

from app.modules.templates.definition import TemplateDefinitionBuilder


def test_decorate_concept_description_sets_unit_kind_when_uom_present() -> None:
    builder = TemplateDefinitionBuilder(
        uom_by_cd_id={
            "urn:unit:m": {
                "symbol": "m",
                "specificUnitID": "MTR",
                "classificationSystem": "UNECE Rec 20",
            }
        },
        validation_by_cd_id={
            "urn:unit:m": [
                {
                    "code": "sample_warning",
                    "severity": "warning",
                }
            ]
        },
    )

    result = builder._decorate_concept_description({"id": "urn:unit:m"})

    assert result["kind"] == "unit"
    assert result["unitResolutionStatus"] == "resolved"
    assert result["uom"]["symbol"] == "m"
    assert result["x_validation"][0]["code"] == "sample_warning"


def test_decorate_concept_description_sets_unresolved_for_unknown_unit_reference() -> None:
    builder = TemplateDefinitionBuilder()

    result = builder._decorate_concept_description(
        {
            "id": "urn:cd:length",
            "unitId": "urn:unit:missing",
        }
    )

    assert result["kind"] == "concept"
    assert result["unitResolutionStatus"] == "unresolved"
