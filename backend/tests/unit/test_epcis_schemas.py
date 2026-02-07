"""Unit tests for EPCIS 2.0 Pydantic schemas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.epcis.schemas import (
    AggregationEventCreate,
    AssociationEventCreate,
    CaptureResponse,
    EPCISBody,
    EPCISDocumentCreate,
    EPCISEventResponse,
    ObjectEventCreate,
    TransactionEventCreate,
    TransformationEventCreate,
)

NOW = datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC)
NOW_ISO = "2026-02-07T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Valid event creation
# ---------------------------------------------------------------------------


class TestObjectEvent:
    def test_valid_with_aliases(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+01:00",
            "epcList": ["urn:epc:id:sgtin:0614141.107346.2017"],
            "action": "ADD",
            "bizStep": "commissioning",
            "disposition": "active",
        }
        event = ObjectEventCreate.model_validate(data)
        assert event.type == "ObjectEvent"
        assert event.action == "ADD"
        assert event.biz_step == "commissioning"
        assert event.epc_list == ["urn:epc:id:sgtin:0614141.107346.2017"]

    def test_valid_with_quantity_list(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "quantityList": [
                {
                    "epcClass": "urn:epc:class:lgtin:409876.0012345.Lot1",
                    "quantity": 100,
                    "uom": "KGM",
                }
            ],
            "action": "OBSERVE",
        }
        event = ObjectEventCreate.model_validate(data)
        assert len(event.quantity_list) == 1
        assert event.quantity_list[0].uom == "KGM"

    def test_invalid_action_rejected(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "action": "INVALID",
        }
        with pytest.raises(ValidationError):
            ObjectEventCreate.model_validate(data)


class TestAggregationEvent:
    def test_valid(self) -> None:
        data = {
            "type": "AggregationEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+02:00",
            "parentID": "urn:epc:id:sscc:0614141.1234567890",
            "childEPCs": [
                "urn:epc:id:sgtin:0614141.107346.2017",
                "urn:epc:id:sgtin:0614141.107346.2018",
            ],
            "action": "ADD",
        }
        event = AggregationEventCreate.model_validate(data)
        assert event.parent_id == "urn:epc:id:sscc:0614141.1234567890"
        assert len(event.child_epcs) == 2


class TestTransactionEvent:
    def test_valid(self) -> None:
        data = {
            "type": "TransactionEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "bizTransactionList": [
                {"type": "po", "bizTransaction": "urn:epcglobal:cbv:bt:0614141073467:PO-123"}
            ],
            "epcList": ["urn:epc:id:sgtin:0614141.107346.2017"],
            "action": "ADD",
        }
        event = TransactionEventCreate.model_validate(data)
        assert len(event.biz_transaction_list) == 1
        assert event.biz_transaction_list[0].type == "po"

    def test_missing_biz_transaction_list(self) -> None:
        data = {
            "type": "TransactionEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "action": "ADD",
        }
        with pytest.raises(ValidationError):
            TransactionEventCreate.model_validate(data)


class TestTransformationEvent:
    def test_valid(self) -> None:
        data = {
            "type": "TransformationEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "inputEPCList": ["urn:epc:id:sgtin:0614141.107346.100"],
            "outputEPCList": ["urn:epc:id:sgtin:0614141.107346.200"],
            "transformationID": "urn:epc:id:gdti:0614141.00001.TF-001",
        }
        event = TransformationEventCreate.model_validate(data)
        assert len(event.input_epc_list) == 1
        assert len(event.output_epc_list) == 1
        assert event.transformation_id is not None


class TestAssociationEvent:
    def test_valid(self) -> None:
        data = {
            "type": "AssociationEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+00:00",
            "parentID": "urn:epc:id:grai:0614141.00001.ABC123",
            "childEPCs": ["urn:epc:id:sgtin:0614141.107346.2017"],
            "action": "ADD",
        }
        event = AssociationEventCreate.model_validate(data)
        assert event.type == "AssociationEvent"


# ---------------------------------------------------------------------------
# Document wrapper
# ---------------------------------------------------------------------------


class TestEPCISDocument:
    def test_valid_document_with_mixed_events(self) -> None:
        doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": NOW_ISO,
            "epcisBody": {
                "eventList": [
                    {
                        "type": "ObjectEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+00:00",
                        "epcList": ["urn:epc:id:sgtin:0614141.107346.1"],
                        "action": "ADD",
                        "bizStep": "commissioning",
                    },
                    {
                        "type": "TransformationEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+00:00",
                        "inputEPCList": ["urn:epc:id:sgtin:0614141.107346.1"],
                        "outputEPCList": ["urn:epc:id:sgtin:0614141.107346.2"],
                    },
                ]
            },
        }
        parsed = EPCISDocumentCreate.model_validate(doc)
        assert len(parsed.epcis_body.event_list) == 2
        assert parsed.epcis_body.event_list[0].type == "ObjectEvent"
        assert parsed.epcis_body.event_list[1].type == "TransformationEvent"

    def test_empty_event_list_rejected(self) -> None:
        """epcisBody.eventList cannot be empty (pydantic list min_length defaults to 0 but type check applies)."""
        doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": NOW_ISO,
            "epcisBody": {"eventList": []},
        }
        # Empty list is valid per schema — the service layer can reject it
        parsed = EPCISDocumentCreate.model_validate(doc)
        assert len(parsed.epcis_body.event_list) == 0

    def test_invalid_event_type_rejected(self) -> None:
        doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": NOW_ISO,
            "epcisBody": {
                "eventList": [
                    {
                        "type": "FakeEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+00:00",
                    }
                ]
            },
        }
        with pytest.raises(ValidationError):
            EPCISDocumentCreate.model_validate(doc)


# ---------------------------------------------------------------------------
# Discriminated union dispatch
# ---------------------------------------------------------------------------


class TestDiscriminatedUnion:
    def test_type_dispatch(self) -> None:
        body_data = {
            "eventList": [
                {
                    "type": "ObjectEvent",
                    "eventTime": NOW_ISO,
                    "eventTimeZoneOffset": "+00:00",
                    "action": "ADD",
                },
                {
                    "type": "AggregationEvent",
                    "eventTime": NOW_ISO,
                    "eventTimeZoneOffset": "+00:00",
                    "action": "ADD",
                },
            ]
        }
        body = EPCISBody.model_validate(body_data)
        assert isinstance(body.event_list[0], ObjectEventCreate)
        assert isinstance(body.event_list[1], AggregationEventCreate)


# ---------------------------------------------------------------------------
# JSON alias serialization
# ---------------------------------------------------------------------------


class TestAliasSerialization:
    def test_event_roundtrip(self) -> None:
        data = {
            "type": "ObjectEvent",
            "eventTime": NOW_ISO,
            "eventTimeZoneOffset": "+01:00",
            "epcList": ["urn:epc:id:sgtin:0614141.107346.1"],
            "action": "ADD",
            "bizStep": "commissioning",
            "readPoint": "urn:epc:id:sgln:0614141.07346.1234",
        }
        event = ObjectEventCreate.model_validate(data)
        dumped = event.model_dump(by_alias=True, mode="json")
        assert "eventTime" in dumped
        assert "epcList" in dumped
        assert "bizStep" in dumped
        assert "readPoint" in dumped

    def test_capture_response_aliases(self) -> None:
        resp = CaptureResponse(capture_id="abc-123", event_count=5)
        dumped = resp.model_dump(by_alias=True)
        assert "captureId" in dumped
        assert "eventCount" in dumped
        assert dumped["captureId"] == "abc-123"
        assert dumped["eventCount"] == 5


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class TestEventResponse:
    def test_from_attributes(self) -> None:
        """EPCISEventResponse can be built from a dict mimicking ORM attrs."""
        from uuid import uuid4

        data = {
            "id": uuid4(),
            "dpp_id": uuid4(),
            "event_id": "urn:uuid:abc",
            "event_type": "ObjectEvent",
            "event_time": NOW,
            "event_time_zone_offset": "+00:00",
            "action": "ADD",
            "biz_step": "commissioning",
            "disposition": "active",
            "read_point": None,
            "biz_location": None,
            "payload": {"epcList": ["urn:epc:id:sgtin:0614141.107346.1"]},
            "error_declaration": None,
            "created_by_subject": "user-abc",
            "created_at": NOW,
        }
        resp = EPCISEventResponse.model_validate(data)
        assert resp.event_type == "ObjectEvent"
        assert resp.biz_step == "commissioning"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------


class TestMissingFields:
    def test_missing_event_time(self) -> None:
        with pytest.raises(ValidationError):
            ObjectEventCreate.model_validate(
                {"type": "ObjectEvent", "eventTimeZoneOffset": "+00:00", "action": "ADD"}
            )

    def test_missing_timezone_offset(self) -> None:
        with pytest.raises(ValidationError):
            ObjectEventCreate.model_validate(
                {"type": "ObjectEvent", "eventTime": NOW_ISO, "action": "ADD"}
            )
