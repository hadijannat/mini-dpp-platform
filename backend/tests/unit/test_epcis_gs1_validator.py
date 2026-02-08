"""Unit tests for GS1 structural validation of EPCIS events."""

from __future__ import annotations

from app.modules.epcis.gs1_validator import validate_against_gs1_schema


def _base_event(event_type: str, **overrides: object) -> dict[str, object]:
    """Build a minimal valid event dict for testing."""
    event: dict[str, object] = {
        "type": event_type,
        "eventTime": "2025-01-15T10:00:00Z",
        "eventTimeZoneOffset": "+02:00",
    }
    event.update(overrides)
    return event


class TestAlwaysRequiredFields:
    def test_valid_minimal_object_event(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        errors = validate_against_gs1_schema(event)
        # Should have no structural errors (EPC warnings are separate)
        structural = [e for e in errors if "(warning)" not in e]
        assert structural == []

    def test_missing_event_time(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        del event["eventTime"]
        errors = validate_against_gs1_schema(event)
        assert any("eventTime" in e for e in errors)

    def test_missing_event_time_zone_offset(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        del event["eventTimeZoneOffset"]
        errors = validate_against_gs1_schema(event)
        assert any("eventTimeZoneOffset" in e for e in errors)

    def test_missing_type(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        del event["type"]
        errors = validate_against_gs1_schema(event)
        assert any("type" in e for e in errors)


class TestTimezoneOffsetFormat:
    def test_valid_positive(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        event["eventTimeZoneOffset"] = "+05:30"
        errors = validate_against_gs1_schema(event)
        structural = [e for e in errors if "eventTimeZoneOffset format" in e]
        assert structural == []

    def test_valid_negative(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        event["eventTimeZoneOffset"] = "-08:00"
        errors = validate_against_gs1_schema(event)
        structural = [e for e in errors if "eventTimeZoneOffset format" in e]
        assert structural == []

    def test_valid_z(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        event["eventTimeZoneOffset"] = "Z"
        errors = validate_against_gs1_schema(event)
        structural = [e for e in errors if "eventTimeZoneOffset format" in e]
        assert structural == []

    def test_invalid_format(self) -> None:
        event = _base_event("ObjectEvent", action="OBSERVE")
        event["eventTimeZoneOffset"] = "UTC+2"
        errors = validate_against_gs1_schema(event)
        assert any("eventTimeZoneOffset format" in e for e in errors)


class TestActionField:
    def test_object_event_requires_action(self) -> None:
        event = _base_event("ObjectEvent")
        errors = validate_against_gs1_schema(event)
        assert any("requires an 'action'" in e for e in errors)

    def test_aggregation_event_requires_action(self) -> None:
        event = _base_event("AggregationEvent")
        errors = validate_against_gs1_schema(event)
        assert any("requires an 'action'" in e for e in errors)

    def test_transaction_event_requires_action(self) -> None:
        event = _base_event(
            "TransactionEvent",
            bizTransactionList=[{"type": "po", "bizTransaction": "urn:epc:id:gdti:1234"}],
        )
        errors = validate_against_gs1_schema(event)
        assert any("requires an 'action'" in e for e in errors)

    def test_association_event_requires_action(self) -> None:
        event = _base_event("AssociationEvent")
        errors = validate_against_gs1_schema(event)
        assert any("requires an 'action'" in e for e in errors)

    def test_transformation_event_must_not_have_action(self) -> None:
        event = _base_event("TransformationEvent", action="ADD")
        errors = validate_against_gs1_schema(event)
        assert any("must NOT have an 'action'" in e for e in errors)

    def test_transformation_event_ok_without_action(self) -> None:
        event = _base_event("TransformationEvent")
        errors = validate_against_gs1_schema(event)
        structural = [e for e in errors if "(warning)" not in e]
        assert structural == []

    def test_invalid_action_value(self) -> None:
        event = _base_event("ObjectEvent", action="INVALID")
        errors = validate_against_gs1_schema(event)
        assert any("Invalid action value" in e for e in errors)

    def test_valid_action_add(self) -> None:
        event = _base_event("ObjectEvent", action="ADD")
        errors = validate_against_gs1_schema(event)
        assert not any("action" in e.lower() for e in errors if "(warning)" not in e)

    def test_valid_action_delete(self) -> None:
        event = _base_event("ObjectEvent", action="DELETE")
        errors = validate_against_gs1_schema(event)
        assert not any("action" in e.lower() for e in errors if "(warning)" not in e)


class TestTypeSpecificValidation:
    def test_transaction_event_requires_biz_transaction_list(self) -> None:
        event = _base_event("TransactionEvent", action="ADD")
        errors = validate_against_gs1_schema(event)
        assert any("bizTransactionList" in e for e in errors)

    def test_transaction_event_with_biz_list(self) -> None:
        event = _base_event(
            "TransactionEvent",
            action="ADD",
            bizTransactionList=[{"type": "po", "bizTransaction": "urn:epc:id:gdti:1234"}],
        )
        errors = validate_against_gs1_schema(event)
        structural = [e for e in errors if "(warning)" not in e]
        assert structural == []


class TestEPCUriWarnings:
    def test_valid_epc_uri_no_warning(self) -> None:
        event = _base_event(
            "ObjectEvent",
            action="OBSERVE",
            epcList=["urn:epc:id:sgtin:0614141.107346.2017"],
        )
        errors = validate_against_gs1_schema(event)
        assert not any("warning" in e for e in errors)

    def test_non_urn_epc_generates_warning(self) -> None:
        event = _base_event(
            "ObjectEvent",
            action="OBSERVE",
            epcList=["https://example.com/product/123"],
        )
        errors = validate_against_gs1_schema(event)
        assert any("urn:epc:" in e and "(warning)" in e for e in errors)

    def test_parent_id_warning(self) -> None:
        event = _base_event(
            "AggregationEvent",
            action="ADD",
            parentID="https://example.com/container/1",
        )
        errors = validate_against_gs1_schema(event)
        assert any("parentID" in e and "(warning)" in e for e in errors)

    def test_valid_parent_id_no_warning(self) -> None:
        event = _base_event(
            "AggregationEvent",
            action="ADD",
            parentID="urn:epc:id:sscc:0614141.1677777777",
        )
        errors = validate_against_gs1_schema(event)
        assert not any("parentID" in e for e in errors)
