"""E2E tests for the EPCIS 2.0 capture and query flow.

Requires a running backend stack (docker compose up).
"""

from __future__ import annotations

from datetime import datetime, timezone

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


NOW_ISO = datetime.now(tz=timezone.utc).isoformat()


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
