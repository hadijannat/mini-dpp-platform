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
            "template_key": "digital-nameplate",
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
        public_client = httpx.Client(
            base_url=runtime.dpp_base_url, timeout=30.0
        )
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
        public_client = httpx.Client(
            base_url=runtime.dpp_base_url, timeout=30.0
        )
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
            f"/api/v1/tenants/{slug}/epcis/events"
            f"?dpp_id={dpp_id}&event_type=ObjectEvent",
        )
        assert filt.status_code == 200, filt.text
        filtered = filt.json()["eventList"]
        assert len(filtered) == 1
        assert filtered[0]["event_type"] == "ObjectEvent"
