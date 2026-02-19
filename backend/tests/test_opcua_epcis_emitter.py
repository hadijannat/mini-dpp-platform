"""Tests for the EPCIS event emitter."""

from datetime import UTC, datetime

from app.opcua_agent.epcis_emitter import build_epcis_event_payload


def test_build_epcis_event_payload():
    payload = build_epcis_event_payload(
        event_type="ObjectEvent",
        biz_step="urn:epcglobal:cbv:bizstep:inspecting",
        disposition="urn:epcglobal:cbv:disp:in_progress",
        action="OBSERVE",
        read_point="urn:epc:id:sgln:9521234.00001.0",
        biz_location="urn:epc:id:sgln:9521234.00000.0",
        epc_list=["urn:epc:id:sgtin:9521234.00001.1001"],
        event_time=datetime(2026, 2, 19, 12, 0, 0, tzinfo=UTC),
    )
    assert payload["type"] == "ObjectEvent"
    assert payload["bizStep"] == "urn:epcglobal:cbv:bizstep:inspecting"
    assert payload["action"] == "OBSERVE"
    assert len(payload["epcList"]) == 1


def test_build_epcis_event_payload_defaults():
    """Event with minimal args still has required fields."""
    payload = build_epcis_event_payload(event_type="ObjectEvent")
    assert payload["type"] == "ObjectEvent"
    assert payload["action"] == "OBSERVE"
    assert "eventTime" in payload
    assert "eventTimeZoneOffset" in payload
    assert "bizStep" not in payload
    assert "epcList" not in payload


def test_build_epcis_event_payload_source_event_id():
    """source_event_id is included when provided."""
    payload = build_epcis_event_payload(
        event_type="ObjectEvent",
        source_event_id="opcua-trigger-001",
    )
    assert payload["sourceEventId"] == "opcua-trigger-001"
