"""Unit tests for the EPCIS -> AAS Traceability submodel bridge."""

from __future__ import annotations

import types
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.modules.epcis.aas_bridge import (
    TRACEABILITY_ID_SHORT,
    TRACEABILITY_SEMANTIC_ID,
    build_traceability_submodel,
)
from app.modules.epcis.schemas import EPCISEventResponse
from app.modules.export.service import ExportService


def _make_event(
    *,
    event_type: str = "ObjectEvent",
    action: str | None = "OBSERVE",
    biz_step: str | None = "shipping",
    disposition: str | None = "in_transit",
    read_point: str | None = None,
    biz_location: str | None = None,
    payload: dict[str, Any] | None = None,
    event_time: datetime | None = None,
) -> EPCISEventResponse:
    return EPCISEventResponse(
        id=uuid4(),
        dpp_id=uuid4(),
        event_id=f"urn:uuid:{uuid4()}",
        event_type=event_type,
        event_time=event_time or datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC),
        event_time_zone_offset="+01:00",
        action=action,
        biz_step=biz_step,
        disposition=disposition,
        read_point=read_point,
        biz_location=biz_location,
        payload=payload or {},
        error_declaration=None,
        created_by_subject="test",
        created_at=datetime(2026, 2, 7, 10, 0, 0, tzinfo=UTC),
    )


def _find_element(elements: list[dict[str, Any]], id_short: str) -> dict[str, Any] | None:
    """Find an element by idShort in a list of submodel elements."""
    return next((el for el in elements if el.get("idShort") == id_short), None)


def _get_event_history(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the EventHistory collection from a submodel result."""
    eh = _find_element(result["submodelElements"], "EventHistory")
    assert eh is not None, "EventHistory not found in submodelElements"
    return eh


class TestBuildTraceabilitySubmodel:
    def test_empty_events_returns_none(self) -> None:
        assert build_traceability_submodel([]) is None

    def test_single_event_produces_submodel(self) -> None:
        event = _make_event()
        result = build_traceability_submodel([event])

        assert result is not None
        assert result["idShort"] == TRACEABILITY_ID_SHORT
        assert result["id"] == TRACEABILITY_SEMANTIC_ID
        assert result["modelType"] == "Submodel"

        # Event is inside EventHistory wrapper
        event_history = _get_event_history(result)
        assert len(event_history["value"]) == 1

        collection = event_history["value"][0]
        assert collection["idShort"] == "Event001"
        assert collection["modelType"] == "SubmodelElementCollection"

        # Check property values
        props = {
            p["idShort"]: p["value"] for p in collection["value"] if p["modelType"] == "Property"
        }
        assert props["EventType"] == "ObjectEvent"
        assert props["Action"] == "OBSERVE"
        assert props["BizStep"] == "shipping"
        assert props["Disposition"] == "in_transit"

    def test_three_events_produce_three_collections(self) -> None:
        events = [
            _make_event(event_type="ObjectEvent", biz_step="commissioning"),
            _make_event(event_type="AggregationEvent", biz_step="packing", action="ADD"),
            _make_event(event_type="TransformationEvent", biz_step="transforming", action=None),
        ]
        result = build_traceability_submodel(events)

        assert result is not None
        event_history = _get_event_history(result)
        assert len(event_history["value"]) == 3
        assert event_history["value"][0]["idShort"] == "Event001"
        assert event_history["value"][1]["idShort"] == "Event002"
        assert event_history["value"][2]["idShort"] == "Event003"

    def test_optional_fields_omitted_when_none(self) -> None:
        event = _make_event(
            action=None,
            biz_step=None,
            disposition=None,
            read_point=None,
            biz_location=None,
        )
        result = build_traceability_submodel([event])
        assert result is not None

        event_history = _get_event_history(result)
        collection = event_history["value"][0]
        prop_names = {p["idShort"] for p in collection["value"] if p["modelType"] == "Property"}
        assert "EventType" in prop_names
        assert "EventTime" in prop_names
        assert "Action" not in prop_names
        assert "BizStep" not in prop_names
        assert "Disposition" not in prop_names

    def test_read_point_and_biz_location_included(self) -> None:
        event = _make_event(
            read_point="urn:epc:id:sgln:0614141.00777.0",
            biz_location="urn:epc:id:sgln:0614141.00888.0",
        )
        result = build_traceability_submodel([event])
        assert result is not None

        event_history = _get_event_history(result)
        collection = event_history["value"][0]
        props = {
            p["idShort"]: p["value"] for p in collection["value"] if p["modelType"] == "Property"
        }
        assert props["ReadPoint"] == "urn:epc:id:sgln:0614141.00777.0"
        assert props["BizLocation"] == "urn:epc:id:sgln:0614141.00888.0"

    def test_payload_epc_list_nested(self) -> None:
        event = _make_event(
            payload={
                "epcList": [
                    "urn:epc:id:sgtin:001.002.003",
                    "urn:epc:id:sgtin:001.002.004",
                ],
                "parentID": "urn:epc:id:sscc:0614141.1234567890",
            }
        )
        result = build_traceability_submodel([event])
        assert result is not None

        event_history = _get_event_history(result)
        collection = event_history["value"][0]
        # Find the Payload sub-collection
        payload_coll = next(
            (el for el in collection["value"] if el.get("idShort") == "Payload"),
            None,
        )
        assert payload_coll is not None
        assert payload_coll["modelType"] == "SubmodelElementCollection"

        payload_props = {p["idShort"]: p["value"] for p in payload_coll["value"]}
        assert "epcList" in payload_props
        assert "urn:epc:id:sgtin:001.002.003" in payload_props["epcList"]
        assert "ParentID" in payload_props
        assert payload_props["ParentID"] == "urn:epc:id:sscc:0614141.1234567890"

    def test_semantic_id_structure(self) -> None:
        event = _make_event()
        result = build_traceability_submodel([event])
        assert result is not None

        sem_id = result["semanticId"]
        assert sem_id["type"] == "ExternalReference"
        assert len(sem_id["keys"]) == 1
        assert sem_id["keys"][0]["type"] == "GlobalReference"
        assert sem_id["keys"][0]["value"] == TRACEABILITY_SEMANTIC_ID


class TestEventHistoryWrapper:
    """Tests for the EventHistory SubmodelElementCollection wrapper."""

    def test_event_history_present(self) -> None:
        result = build_traceability_submodel([_make_event()])
        assert result is not None

        event_history = _find_element(result["submodelElements"], "EventHistory")
        assert event_history is not None
        assert event_history["modelType"] == "SubmodelElementCollection"

    def test_event_history_contains_all_events(self) -> None:
        events = [_make_event() for _ in range(5)]
        result = build_traceability_submodel(events)
        assert result is not None

        event_history = _get_event_history(result)
        assert len(event_history["value"]) == 5
        for i, coll in enumerate(event_history["value"]):
            assert coll["idShort"] == f"Event{i + 1:03d}"


class TestEPCISEndpoint:
    """Tests for the EPCISEndpoint property."""

    def test_epcis_endpoint_present_when_provided(self) -> None:
        url = "https://example.com/api/v1/public/acme/epcis/events/123"
        result = build_traceability_submodel([_make_event()], epcis_endpoint_url=url)
        assert result is not None

        prop = _find_element(result["submodelElements"], "EPCISEndpoint")
        assert prop is not None
        assert prop["modelType"] == "Property"
        assert prop["valueType"] == "xs:anyURI"
        assert prop["value"] == url

    def test_epcis_endpoint_absent_when_not_provided(self) -> None:
        result = build_traceability_submodel([_make_event()])
        assert result is not None

        prop = _find_element(result["submodelElements"], "EPCISEndpoint")
        assert prop is None


class TestDigitalLinkURI:
    """Tests for the DigitalLinkURI property."""

    def test_digital_link_uri_present_when_provided(self) -> None:
        uri = "https://id.gs1.org/01/09506000134352"
        result = build_traceability_submodel([_make_event()], digital_link_uri=uri)
        assert result is not None

        prop = _find_element(result["submodelElements"], "DigitalLinkURI")
        assert prop is not None
        assert prop["modelType"] == "Property"
        assert prop["valueType"] == "xs:anyURI"
        assert prop["value"] == uri

    def test_digital_link_uri_absent_when_not_provided(self) -> None:
        result = build_traceability_submodel([_make_event()])
        assert result is not None

        prop = _find_element(result["submodelElements"], "DigitalLinkURI")
        assert prop is None


class TestLatestEventSummary:
    """Tests for the LatestEventSummary SubmodelElementCollection."""

    def test_summary_from_single_event(self) -> None:
        event = _make_event(
            event_type="ObjectEvent",
            biz_step="shipping",
            disposition="in_transit",
            biz_location="urn:epc:id:sgln:0614141.00888.0",
        )
        result = build_traceability_submodel([event])
        assert result is not None

        summary = _find_element(result["submodelElements"], "LatestEventSummary")
        assert summary is not None
        assert summary["modelType"] == "SubmodelElementCollection"

        props = {p["idShort"]: p["value"] for p in summary["value"]}
        assert props["LastEventType"] == "ObjectEvent"
        assert props["LastEventTime"] == event.event_time.isoformat()
        assert props["LastBizStep"] == "shipping"
        assert props["LastDisposition"] == "in_transit"
        assert props["LastLocation"] == "urn:epc:id:sgln:0614141.00888.0"
        assert props["TotalEventCount"] == "1"

    def test_summary_picks_last_event(self) -> None:
        events = [
            _make_event(
                event_type="ObjectEvent",
                biz_step="commissioning",
                event_time=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            _make_event(
                event_type="AggregationEvent",
                biz_step="packing",
                action="ADD",
                event_time=datetime(2026, 2, 1, tzinfo=UTC),
            ),
            _make_event(
                event_type="TransformationEvent",
                biz_step="transforming",
                action=None,
                disposition="active",
                event_time=datetime(2026, 2, 7, tzinfo=UTC),
            ),
        ]
        result = build_traceability_submodel(events)
        assert result is not None

        summary = _find_element(result["submodelElements"], "LatestEventSummary")
        assert summary is not None

        props = {p["idShort"]: p["value"] for p in summary["value"]}
        assert props["LastEventType"] == "TransformationEvent"
        assert props["LastBizStep"] == "transforming"
        assert props["LastDisposition"] == "active"
        assert props["TotalEventCount"] == "3"

    def test_summary_omits_optional_fields_when_none(self) -> None:
        event = _make_event(
            biz_step=None,
            disposition=None,
            biz_location=None,
        )
        result = build_traceability_submodel([event])
        assert result is not None

        summary = _find_element(result["submodelElements"], "LatestEventSummary")
        assert summary is not None

        prop_names = {p["idShort"] for p in summary["value"]}
        assert "LastEventType" in prop_names
        assert "LastEventTime" in prop_names
        assert "TotalEventCount" in prop_names
        assert "LastBizStep" not in prop_names
        assert "LastDisposition" not in prop_names
        assert "LastLocation" not in prop_names

    def test_total_event_count(self) -> None:
        events = [_make_event() for _ in range(7)]
        result = build_traceability_submodel(events)
        assert result is not None

        summary = _find_element(result["submodelElements"], "LatestEventSummary")
        assert summary is not None

        count_prop = next(p for p in summary["value"] if p["idShort"] == "TotalEventCount")
        assert count_prop["value"] == "7"


class TestInjectTraceabilitySubmodel:
    """Tests for ExportService.inject_traceability_submodel()."""

    @staticmethod
    def _make_revision(
        aas_env_json: dict[str, Any] | None = None,
    ) -> types.SimpleNamespace:
        """Build a lightweight mock DPPRevision."""
        return types.SimpleNamespace(
            aas_env_json=aas_env_json if aas_env_json is not None else {},
        )

    def test_empty_events_no_modification(self) -> None:
        """When epcis_events is empty, aas_env_json should not be modified."""
        revision = self._make_revision({"submodels": [{"idShort": "Existing"}]})
        original = revision.aas_env_json.copy()

        ExportService.inject_traceability_submodel(revision, [])  # type: ignore[arg-type]

        assert revision.aas_env_json == original

    def test_events_append_traceability_submodel(self) -> None:
        """When epcis_events has events, a Traceability submodel should be appended."""
        existing_submodel = {"idShort": "ExistingSubmodel", "modelType": "Submodel"}
        revision = self._make_revision({"submodels": [existing_submodel]})

        events = [_make_event(), _make_event(event_type="AggregationEvent", action="ADD")]
        ExportService.inject_traceability_submodel(revision, events)  # type: ignore[arg-type]

        submodels = revision.aas_env_json["submodels"]
        assert len(submodels) == 2
        assert submodels[0] == existing_submodel
        assert submodels[1]["idShort"] == TRACEABILITY_ID_SHORT
        assert submodels[1]["modelType"] == "Submodel"

        # Events are inside EventHistory
        event_history = _find_element(submodels[1]["submodelElements"], "EventHistory")
        assert event_history is not None
        assert len(event_history["value"]) == 2

    def test_missing_submodels_key_is_created(self) -> None:
        """When aas_env_json has no 'submodels' key, it should be created."""
        revision = self._make_revision({"assetAdministrationShells": []})

        events = [_make_event()]
        ExportService.inject_traceability_submodel(revision, events)  # type: ignore[arg-type]

        assert "submodels" in revision.aas_env_json
        assert len(revision.aas_env_json["submodels"]) == 1
        assert revision.aas_env_json["submodels"][0]["idShort"] == TRACEABILITY_ID_SHORT

    def test_non_dict_aas_env_is_skipped(self) -> None:
        """When aas_env_json is not a dict, the method should be a no-op."""
        revision = self._make_revision()
        revision.aas_env_json = None

        events = [_make_event()]
        ExportService.inject_traceability_submodel(revision, events)  # type: ignore[arg-type]

        assert revision.aas_env_json is None

    def test_inject_with_epcis_endpoint_url(self) -> None:
        """The epcis_endpoint_url kwarg should be forwarded to the bridge."""
        revision = self._make_revision({})
        url = "https://dpp-platform.dev/api/v1/public/acme/epcis/events/abc"

        ExportService.inject_traceability_submodel(  # type: ignore[arg-type]
            revision,
            [_make_event()],
            epcis_endpoint_url=url,
        )

        submodel = revision.aas_env_json["submodels"][0]
        endpoint = _find_element(submodel["submodelElements"], "EPCISEndpoint")
        assert endpoint is not None
        assert endpoint["value"] == url

    def test_inject_with_digital_link_uri(self) -> None:
        """The digital_link_uri kwarg should be forwarded to the bridge."""
        revision = self._make_revision({})
        uri = "https://id.gs1.org/01/09506000134352"

        ExportService.inject_traceability_submodel(  # type: ignore[arg-type]
            revision,
            [_make_event()],
            digital_link_uri=uri,
        )

        submodel = revision.aas_env_json["submodels"][0]
        link = _find_element(submodel["submodelElements"], "DigitalLinkURI")
        assert link is not None
        assert link["value"] == uri
