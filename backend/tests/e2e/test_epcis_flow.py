"""E2E tests for the EPCIS 2.0 capture and query flow.

Requires a running backend stack (docker compose up).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest


@pytest.fixture(scope="module")
def _dpp_for_epcis(api_client: httpx.Client, runtime: object) -> dict:
    """Create a DPP to attach EPCIS events to."""
    tenant_slug = getattr(runtime, "tenant_slug", "default")
    resp = api_client.post(
        f"/api/v1/tenants/{tenant_slug}/dpps",
        json={
            "asset_ids": {
                "manufacturerPartId": "EPCIS-E2E",
                "serialNumber": "EPCIS-SN-001",
            },
            "selected_templates": ["digital-nameplate"],
        },
    )
    assert resp.status_code in (200, 201), f"Failed to create DPP: {resp.text}"
    return resp.json()


@pytest.fixture(scope="module")
def dpp_id(_dpp_for_epcis: dict) -> str:
    return _dpp_for_epcis["id"]


@pytest.fixture(scope="module")
def tenant_slug(runtime: object) -> str:
    return getattr(runtime, "tenant_slug", "default")


@pytest.fixture(scope="module")
def epcis_base(tenant_slug: str) -> str:
    return f"/api/v1/tenants/{tenant_slug}/epcis"


NOW_ISO = datetime.now(tz=UTC).isoformat()


class TestEPCISCapture:
    def test_capture_object_events(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """POST /epcis/capture with ObjectEvent → 202 with captureId."""
        document = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": NOW_ISO,
            "epcisBody": {
                "eventList": [
                    {
                        "type": "ObjectEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+01:00",
                        "epcList": [f"urn:epc:id:sgtin:0614141.107346.{dpp_id[:8]}"],
                        "action": "ADD",
                        "bizStep": "commissioning",
                        "disposition": "active",
                    },
                    {
                        "type": "ObjectEvent",
                        "eventTime": NOW_ISO,
                        "eventTimeZoneOffset": "+01:00",
                        "epcList": [f"urn:epc:id:sgtin:0614141.107346.{dpp_id[:8]}"],
                        "action": "OBSERVE",
                        "bizStep": "inspecting",
                        "disposition": "conformant",
                    },
                ]
            },
        }
        resp = api_client.post(
            f"{epcis_base}/capture",
            json=document,
            params={"dpp_id": dpp_id},
        )
        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "captureId" in body
        assert body["eventCount"] == 2

    def test_capture_invalid_document(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """POST invalid document → 422."""
        resp = api_client.post(
            f"{epcis_base}/capture",
            json={"invalid": "document"},
            params={"dpp_id": dpp_id},
        )
        assert resp.status_code == 422


class TestEPCISQuery:
    def test_query_events_by_biz_step(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """GET /epcis/events?EQ_bizStep=commissioning."""
        resp = api_client.get(
            f"{epcis_base}/events",
            params={"EQ_bizStep": "commissioning", "dpp_id": dpp_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "eventList" in body
        events = body["eventList"]
        assert len(events) >= 1
        assert all(e["biz_step"] == "commissioning" for e in events)

    def test_query_events_for_dpp(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """GET /epcis/events?dpp_id=... returns events for that DPP."""
        resp = api_client.get(
            f"{epcis_base}/events",
            params={"dpp_id": dpp_id},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        events = body["eventList"]
        assert len(events) >= 2
        assert all(e["dpp_id"] == dpp_id for e in events)

    def test_get_event_by_id(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """GET /epcis/events/{event_id} returns a single event."""
        # First, get an event ID from a query
        resp = api_client.get(
            f"{epcis_base}/events",
            params={"dpp_id": dpp_id, "limit": 1},
        )
        assert resp.status_code == 200
        events = resp.json()["eventList"]
        assert len(events) >= 1

        event_id = events[0]["event_id"]
        detail_resp = api_client.get(f"{epcis_base}/events/{event_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["event_id"] == event_id


# ---------------------------------------------------------------------------
# Public endpoint & filter tests
# ---------------------------------------------------------------------------


def _extract_dpp_id(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("id", "dpp_id"):
            value = payload.get(key)
            if value:
                return str(value)
    raise AssertionError(f"Unable to extract DPP id from response: {payload}")


def _object_event_doc() -> dict:
    return {
        "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
        "type": "EPCISDocument",
        "schemaVersion": "2.0",
        "creationDate": "2026-02-07T10:00:00Z",
        "epcisBody": {
            "eventList": [
                {
                    "type": "ObjectEvent",
                    "eventTime": "2026-02-07T10:00:00Z",
                    "eventTimeZoneOffset": "+01:00",
                    "epcList": ["urn:epc:id:sgtin:0614141.107346.2017"],
                    "action": "OBSERVE",
                    "bizStep": "shipping",
                    "disposition": "in_transit",
                    "readPoint": "urn:epc:id:sgln:0614141.00777.0",
                }
            ]
        },
    }


def _aggregation_event_doc() -> dict:
    return {
        "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
        "type": "EPCISDocument",
        "schemaVersion": "2.0",
        "creationDate": "2026-02-07T11:00:00Z",
        "epcisBody": {
            "eventList": [
                {
                    "type": "AggregationEvent",
                    "eventTime": "2026-02-07T11:00:00Z",
                    "eventTimeZoneOffset": "+01:00",
                    "parentID": "urn:epc:id:sscc:0614141.1234567890",
                    "childEPCs": ["urn:epc:id:sgtin:0614141.107346.2017"],
                    "action": "ADD",
                    "bizStep": "packing",
                    "disposition": "in_progress",
                }
            ]
        },
    }


@pytest.mark.e2e
class TestEPCISPublicEndpoint:
    def test_public_endpoint_returns_events_for_published_dpp(
        self,
        runtime,
        api_client: httpx.Client,
        test_results_dir: Path,
    ) -> None:
        """Capture events, publish DPP, then query via public endpoint (no auth)."""
        artifacts = test_results_dir / "epcis"
        artifacts.mkdir(parents=True, exist_ok=True)

        # 1) Create a DPP
        create = api_client.post(
            f"/api/v1/tenants/{runtime.tenant_slug}/dpps",
            json={
                "asset_ids": {
                    "manufacturerPartId": "EPCIS-PUB-E2E",
                    "serialNumber": "EPCIS-PUB-SN-001",
                },
                "selected_templates": ["digital-nameplate"],
            },
        )
        assert create.status_code in (200, 201), create.text
        dpp_id = _extract_dpp_id(create.json())

        # 2) Capture an event
        cap = api_client.post(
            f"/api/v1/tenants/{runtime.tenant_slug}/epcis/capture?dpp_id={dpp_id}",
            json=_object_event_doc(),
        )
        assert cap.status_code == 202, cap.text

        # 3) Publish the DPP
        pub = api_client.post(
            f"/api/v1/tenants/{runtime.tenant_slug}/dpps/{dpp_id}/publish",
        )
        assert pub.status_code in (200, 201), pub.text

        # 4) Query via public endpoint (no auth)
        public_client = httpx.Client(base_url=runtime.dpp_base_url, timeout=30.0)
        try:
            resp = public_client.get(
                f"/api/v1/public/{runtime.tenant_slug}/epcis/events/{dpp_id}",
            )
        finally:
            public_client.close()

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["type"] == "EPCISQueryDocument"
        assert len(body["eventList"]) >= 1
        assert body["eventList"][0]["dpp_id"] == dpp_id

        (artifacts / f"{dpp_id}.public-epcis.json").write_text(
            json.dumps(body, indent=2), encoding="utf-8"
        )

    def test_public_endpoint_404_for_draft_dpp(
        self,
        runtime,
        api_client: httpx.Client,
    ) -> None:
        """Draft DPPs should not expose EPCIS events publicly."""
        # Create a draft DPP (don't publish)
        create = api_client.post(
            f"/api/v1/tenants/{runtime.tenant_slug}/dpps",
            json={
                "asset_ids": {
                    "manufacturerPartId": "EPCIS-DRAFT-E2E",
                    "serialNumber": "EPCIS-DRAFT-SN-001",
                },
                "selected_templates": ["digital-nameplate"],
            },
        )
        assert create.status_code in (200, 201), create.text
        dpp_id = _extract_dpp_id(create.json())

        # Query via public endpoint — should 404
        public_client = httpx.Client(base_url=runtime.dpp_base_url, timeout=30.0)
        try:
            resp = public_client.get(
                f"/api/v1/public/{runtime.tenant_slug}/epcis/events/{dpp_id}",
            )
        finally:
            public_client.close()

        assert resp.status_code == 404


@pytest.mark.e2e
class TestEPCISFilterByType:
    def test_filter_returns_only_matching_type(
        self,
        runtime,
        api_client: httpx.Client,
    ) -> None:
        """Capture ObjectEvent + AggregationEvent, filter by type → only one."""
        slug = runtime.tenant_slug

        # 1) Create DPP
        create = api_client.post(
            f"/api/v1/tenants/{slug}/dpps",
            json={
                "asset_ids": {
                    "manufacturerPartId": "EPCIS-FILT-E2E",
                    "serialNumber": "EPCIS-FILT-SN-001",
                },
                "selected_templates": ["digital-nameplate"],
            },
        )
        assert create.status_code in (200, 201), create.text
        dpp_id = _extract_dpp_id(create.json())

        # 2) Capture ObjectEvent
        c1 = api_client.post(
            f"/api/v1/tenants/{slug}/epcis/capture?dpp_id={dpp_id}",
            json=_object_event_doc(),
        )
        assert c1.status_code == 202, c1.text

        # 3) Capture AggregationEvent
        c2 = api_client.post(
            f"/api/v1/tenants/{slug}/epcis/capture?dpp_id={dpp_id}",
            json=_aggregation_event_doc(),
        )
        assert c2.status_code == 202, c2.text

        # 4) All events → 2
        all_resp = api_client.get(
            f"/api/v1/tenants/{slug}/epcis/events?dpp_id={dpp_id}",
        )
        assert all_resp.status_code == 200, all_resp.text
        assert len(all_resp.json()["eventList"]) == 2

        # 5) Filter by ObjectEvent → 1
        filt = api_client.get(
            f"/api/v1/tenants/{slug}/epcis/events?dpp_id={dpp_id}&event_type=ObjectEvent",
        )
        assert filt.status_code == 200, filt.text
        filtered = filt.json()["eventList"]
        assert len(filtered) == 1
        assert filtered[0]["event_type"] == "ObjectEvent"


# ---------------------------------------------------------------------------
# Named query endpoint tests
# ---------------------------------------------------------------------------


def _transformation_event_doc() -> dict:
    return {
        "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
        "type": "EPCISDocument",
        "schemaVersion": "2.0",
        "creationDate": "2026-02-07T12:00:00Z",
        "epcisBody": {
            "eventList": [
                {
                    "type": "TransformationEvent",
                    "eventTime": "2026-02-07T12:00:00Z",
                    "eventTimeZoneOffset": "+01:00",
                    "inputEPCList": ["urn:epc:id:sgtin:0614141.107346.IN01"],
                    "outputEPCList": ["urn:epc:id:sgtin:0614141.107346.OUT01"],
                    "bizStep": "commissioning",
                    "disposition": "active",
                }
            ]
        },
    }


@pytest.mark.e2e
class TestNamedQueryEndpoints:
    """HTTP-level tests for EPCIS named query CRUD + execution."""

    def test_create_named_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """POST /queries → 201, verify response shape."""
        resp = api_client.post(
            f"{epcis_base}/queries",
            json={
                "name": "test-commissioning",
                "description": "Find commissioning events",
                "query_params": {
                    "eq_biz_step": "commissioning",
                    "dpp_id": dpp_id,
                },
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "test-commissioning"
        assert body["description"] == "Find commissioning events"
        assert "id" in body
        assert "query_params" in body
        assert "created_at" in body

    def test_create_duplicate_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
        dpp_id: str,
    ) -> None:
        """POST same name → 409."""
        resp = api_client.post(
            f"{epcis_base}/queries",
            json={
                "name": "test-commissioning",
                "query_params": {"dpp_id": dpp_id},
            },
        )
        assert resp.status_code == 409, resp.text

    def test_list_named_queries(
        self,
        api_client: httpx.Client,
        epcis_base: str,
    ) -> None:
        """GET /queries → 200, verify list contains created query."""
        resp = api_client.get(f"{epcis_base}/queries")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert isinstance(body, list)
        names = [q["name"] for q in body]
        assert "test-commissioning" in names

    def test_execute_named_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
    ) -> None:
        """GET /queries/{name}/events → 200, verify result shape."""
        resp = api_client.get(f"{epcis_base}/queries/test-commissioning/events")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "eventList" in body
        assert isinstance(body["eventList"], list)

    def test_execute_nonexistent_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
    ) -> None:
        """GET /queries/missing/events → 404."""
        resp = api_client.get(f"{epcis_base}/queries/no-such-query/events")
        assert resp.status_code == 404, resp.text

    def test_delete_named_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
    ) -> None:
        """DELETE /queries/{name} → 204."""
        resp = api_client.delete(f"{epcis_base}/queries/test-commissioning")
        assert resp.status_code == 204, resp.text

    def test_delete_nonexistent_query(
        self,
        api_client: httpx.Client,
        epcis_base: str,
    ) -> None:
        """DELETE /queries/missing → 404."""
        resp = api_client.delete(f"{epcis_base}/queries/no-such-query")
        assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# JSONB query filter integration tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestEPCISQueryFilters:
    """Integration tests for JSONB-based query filters across event types."""

    @pytest.fixture(autouse=True)
    def _setup_filter_data(
        self,
        runtime,
        api_client: httpx.Client,
    ) -> None:
        """Create a DPP and capture diverse events for filter testing."""
        slug = runtime.tenant_slug
        self.slug = slug

        # Create DPP
        create = api_client.post(
            f"/api/v1/tenants/{slug}/dpps",
            json={
                "asset_ids": {
                    "manufacturerPartId": "EPCIS-JSONB-E2E",
                    "serialNumber": "EPCIS-JSONB-SN-001",
                },
                "selected_templates": ["digital-nameplate"],
            },
        )
        assert create.status_code in (200, 201), create.text
        self.filter_dpp_id = _extract_dpp_id(create.json())
        self.epcis_base = f"/api/v1/tenants/{slug}/epcis"

        # Capture ObjectEvent with epcList + action=ADD
        obj_doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": "2026-02-07T10:00:00Z",
            "epcisBody": {
                "eventList": [
                    {
                        "type": "ObjectEvent",
                        "eventTime": "2026-02-07T10:00:00Z",
                        "eventTimeZoneOffset": "+01:00",
                        "epcList": ["urn:epc:id:sgtin:0614141.107346.JSONB01"],
                        "action": "ADD",
                        "bizStep": "commissioning",
                        "disposition": "active",
                    }
                ]
            },
        }
        r1 = api_client.post(
            f"{self.epcis_base}/capture?dpp_id={self.filter_dpp_id}",
            json=obj_doc,
        )
        assert r1.status_code == 202, r1.text

        # Capture AggregationEvent with childEPCs + parentID
        agg_doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": "2026-02-07T11:00:00Z",
            "epcisBody": {
                "eventList": [
                    {
                        "type": "AggregationEvent",
                        "eventTime": "2026-02-07T11:00:00Z",
                        "eventTimeZoneOffset": "+01:00",
                        "parentID": "urn:epc:id:sscc:0614141.JSONB_PARENT",
                        "childEPCs": ["urn:epc:id:sgtin:0614141.107346.JSONB01"],
                        "action": "OBSERVE",
                        "bizStep": "packing",
                        "disposition": "in_progress",
                    }
                ]
            },
        }
        r2 = api_client.post(
            f"{self.epcis_base}/capture?dpp_id={self.filter_dpp_id}",
            json=agg_doc,
        )
        assert r2.status_code == 202, r2.text

        # Capture TransformationEvent with input/output EPCs
        trans_doc = {
            "@context": ["https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": "2026-02-07T12:00:00Z",
            "epcisBody": {
                "eventList": [
                    {
                        "type": "TransformationEvent",
                        "eventTime": "2026-02-07T12:00:00Z",
                        "eventTimeZoneOffset": "+01:00",
                        "inputEPCList": ["urn:epc:id:sgtin:0614141.107346.INPUT01"],
                        "outputEPCList": ["urn:epc:id:sgtin:0614141.107346.OUTPUT01"],
                        "bizStep": "commissioning",
                        "disposition": "active",
                    }
                ]
            },
        }
        r3 = api_client.post(
            f"{self.epcis_base}/capture?dpp_id={self.filter_dpp_id}",
            json=trans_doc,
        )
        assert r3.status_code == 202, r3.text

    def test_match_any_epc_finds_across_lists(
        self,
        api_client: httpx.Client,
    ) -> None:
        """MATCH_anyEPC finds EPC in both epcList and childEPCs."""
        epc = "urn:epc:id:sgtin:0614141.107346.JSONB01"
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "MATCH_anyEPC": epc,
                "dpp_id": self.filter_dpp_id,
            },
        )
        assert resp.status_code == 200, resp.text
        events = resp.json()["eventList"]
        # Should find in ObjectEvent (epcList) and AggregationEvent (childEPCs)
        assert len(events) >= 2
        types = {e["event_type"] for e in events}
        assert "ObjectEvent" in types
        assert "AggregationEvent" in types

    def test_match_parent_id(
        self,
        api_client: httpx.Client,
    ) -> None:
        """MATCH_parentID finds AggregationEvent by parentID."""
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "MATCH_parentID": "urn:epc:id:sscc:0614141.JSONB_PARENT",
                "dpp_id": self.filter_dpp_id,
            },
        )
        assert resp.status_code == 200, resp.text
        events = resp.json()["eventList"]
        assert len(events) == 1
        assert events[0]["event_type"] == "AggregationEvent"

    def test_match_input_epc(
        self,
        api_client: httpx.Client,
    ) -> None:
        """MATCH_inputEPC finds TransformationEvent by input EPC."""
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "MATCH_inputEPC": "urn:epc:id:sgtin:0614141.107346.INPUT01",
                "dpp_id": self.filter_dpp_id,
            },
        )
        assert resp.status_code == 200, resp.text
        events = resp.json()["eventList"]
        assert len(events) == 1
        assert events[0]["event_type"] == "TransformationEvent"

    def test_match_output_epc(
        self,
        api_client: httpx.Client,
    ) -> None:
        """MATCH_outputEPC finds TransformationEvent by output EPC."""
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "MATCH_outputEPC": "urn:epc:id:sgtin:0614141.107346.OUTPUT01",
                "dpp_id": self.filter_dpp_id,
            },
        )
        assert resp.status_code == 200, resp.text
        events = resp.json()["eventList"]
        assert len(events) == 1
        assert events[0]["event_type"] == "TransformationEvent"

    def test_eq_action_filter(
        self,
        api_client: httpx.Client,
    ) -> None:
        """EQ_action filters by ADD vs OBSERVE."""
        resp_add = api_client.get(
            f"{self.epcis_base}/events",
            params={"EQ_action": "ADD", "dpp_id": self.filter_dpp_id},
        )
        assert resp_add.status_code == 200, resp_add.text
        add_events = resp_add.json()["eventList"]
        assert len(add_events) >= 1
        assert all(e["action"] == "ADD" for e in add_events)

        resp_obs = api_client.get(
            f"{self.epcis_base}/events",
            params={"EQ_action": "OBSERVE", "dpp_id": self.filter_dpp_id},
        )
        assert resp_obs.status_code == 200, resp_obs.text
        obs_events = resp_obs.json()["eventList"]
        assert len(obs_events) >= 1
        assert all(e["action"] == "OBSERVE" for e in obs_events)

    def test_combined_filters(
        self,
        api_client: httpx.Client,
    ) -> None:
        """Combined action + bizStep filters narrow results."""
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "EQ_action": "ADD",
                "EQ_bizStep": "commissioning",
                "dpp_id": self.filter_dpp_id,
            },
        )
        assert resp.status_code == 200, resp.text
        events = resp.json()["eventList"]
        assert len(events) >= 1
        for e in events:
            assert e["action"] == "ADD"
            assert e["biz_step"] == "commissioning"

    def test_time_range_filters(
        self,
        api_client: httpx.Client,
    ) -> None:
        """GE_recordTime / LT_recordTime narrows results by created_at."""
        # Get all events first to establish time bounds
        resp = api_client.get(
            f"{self.epcis_base}/events",
            params={"dpp_id": self.filter_dpp_id},
        )
        assert resp.status_code == 200, resp.text
        all_events = resp.json()["eventList"]
        assert len(all_events) >= 3

        # Query with a far-future LT_recordTime should return all
        resp2 = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "dpp_id": self.filter_dpp_id,
                "LT_recordTime": "2099-12-31T23:59:59Z",
            },
        )
        assert resp2.status_code == 200, resp2.text
        assert len(resp2.json()["eventList"]) >= 3

        # Query with a far-past GE_recordTime + far-future LT should also return all
        resp3 = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "dpp_id": self.filter_dpp_id,
                "GE_recordTime": "2020-01-01T00:00:00Z",
                "LT_recordTime": "2099-12-31T23:59:59Z",
            },
        )
        assert resp3.status_code == 200, resp3.text
        assert len(resp3.json()["eventList"]) >= 3

        # Query with a far-future GE_recordTime should return nothing
        resp4 = api_client.get(
            f"{self.epcis_base}/events",
            params={
                "dpp_id": self.filter_dpp_id,
                "GE_recordTime": "2099-01-01T00:00:00Z",
            },
        )
        assert resp4.status_code == 200, resp4.text
        assert len(resp4.json()["eventList"]) == 0
