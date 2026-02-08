"""Tests for webhook schemas, HMAC signing, and service logic."""

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.webhooks.client import compute_signature, verify_signature
from app.modules.webhooks.schemas import (
    ALL_WEBHOOK_EVENTS,
    DeliveryLogResponse,
    WebhookCreate,
    WebhookResponse,
    WebhookUpdate,
)


# ── HMAC Signing Tests ─────────────────────────────────────────────


class TestHMACSigning:
    """Verify HMAC-SHA256 computation and verification."""

    def test_compute_signature_deterministic(self) -> None:
        payload = b'{"event":"DPP_CREATED","dpp_id":"abc"}'
        secret = "test-secret-key"
        sig1 = compute_signature(payload, secret)
        sig2 = compute_signature(payload, secret)
        assert sig1 == sig2

    def test_compute_signature_matches_stdlib(self) -> None:
        payload = b'{"test": true}'
        secret = "my-secret"
        expected = hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        assert compute_signature(payload, secret) == expected

    def test_verify_signature_correct(self) -> None:
        payload = b'{"event":"DPP_PUBLISHED"}'
        secret = "secret123"
        sig = compute_signature(payload, secret)
        assert verify_signature(payload, secret, sig) is True

    def test_verify_signature_wrong_secret(self) -> None:
        payload = b'{"event":"DPP_PUBLISHED"}'
        sig = compute_signature(payload, "correct-secret")
        assert verify_signature(payload, "wrong-secret", sig) is False

    def test_verify_signature_tampered_payload(self) -> None:
        secret = "secret"
        sig = compute_signature(b'{"original":true}', secret)
        assert verify_signature(b'{"tampered":true}', secret, sig) is False

    def test_different_payloads_different_signatures(self) -> None:
        secret = "key"
        sig1 = compute_signature(b'{"a":1}', secret)
        sig2 = compute_signature(b'{"a":2}', secret)
        assert sig1 != sig2


# ── Schema Validation Tests ────────────────────────────────────────


class TestWebhookSchemas:
    """Validate Pydantic schemas for webhook CRUD."""

    def test_create_valid(self) -> None:
        wh = WebhookCreate(
            url="https://example.com/webhook",
            events=["DPP_CREATED", "DPP_PUBLISHED"],
        )
        assert str(wh.url) == "https://example.com/webhook"
        assert len(wh.events) == 2

    def test_create_requires_https_or_http(self) -> None:
        # Pydantic HttpUrl accepts http and https
        wh = WebhookCreate(url="http://localhost:3000/hook", events=["DPP_CREATED"])
        assert "localhost" in str(wh.url)

    def test_create_rejects_empty_events(self) -> None:
        with pytest.raises(ValidationError):
            WebhookCreate(url="https://example.com", events=[])

    def test_create_rejects_invalid_event(self) -> None:
        with pytest.raises(ValidationError):
            WebhookCreate(
                url="https://example.com",
                events=["INVALID_EVENT"],  # type: ignore[list-item]
            )

    def test_update_all_optional(self) -> None:
        update = WebhookUpdate()
        assert update.url is None
        assert update.events is None
        assert update.active is None

    def test_update_partial(self) -> None:
        update = WebhookUpdate(active=False)
        assert update.active is False
        assert update.url is None

    def test_response_model(self) -> None:
        from datetime import UTC, datetime

        resp = WebhookResponse(
            id=uuid4(),
            url="https://example.com/hook",
            events=["DPP_CREATED"],
            active=True,
            created_by_subject="test-user",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert resp.active is True

    def test_delivery_log_response(self) -> None:
        from datetime import UTC, datetime

        log = DeliveryLogResponse(
            id=uuid4(),
            subscription_id=uuid4(),
            event_type="DPP_CREATED",
            payload={"event": "DPP_CREATED"},
            http_status=200,
            response_body="OK",
            attempt=1,
            success=True,
            error_message=None,
            created_at=datetime.now(UTC),
        )
        assert log.success is True
        assert log.http_status == 200

    def test_delivery_log_connection_failure(self) -> None:
        from datetime import UTC, datetime

        log = DeliveryLogResponse(
            id=uuid4(),
            subscription_id=uuid4(),
            event_type="DPP_PUBLISHED",
            payload={"event": "DPP_PUBLISHED"},
            http_status=None,
            response_body=None,
            attempt=3,
            success=False,
            error_message="Connection timed out",
            created_at=datetime.now(UTC),
        )
        assert log.success is False
        assert log.http_status is None


# ── Event Types Tests ──────────────────────────────────────────────


class TestWebhookEventTypes:
    """Verify event type constants."""

    def test_all_events_list(self) -> None:
        assert len(ALL_WEBHOOK_EVENTS) == 5
        assert "DPP_CREATED" in ALL_WEBHOOK_EVENTS
        assert "DPP_PUBLISHED" in ALL_WEBHOOK_EVENTS
        assert "DPP_ARCHIVED" in ALL_WEBHOOK_EVENTS
        assert "DPP_EXPORTED" in ALL_WEBHOOK_EVENTS
        assert "EPCIS_CAPTURED" in ALL_WEBHOOK_EVENTS


# ── Payload Structure Tests ────────────────────────────────────────


class TestWebhookPayloads:
    """Verify webhook payload structures used by trigger points."""

    def test_dpp_created_payload(self) -> None:
        payload = {
            "event": "DPP_CREATED",
            "dpp_id": str(uuid4()),
            "status": "draft",
            "owner_subject": "test-user",
        }
        # Verify it's JSON-serializable and compact
        compact = json.dumps(payload, separators=(",", ":"))
        assert "DPP_CREATED" in compact
        assert '"status":"draft"' in compact

    def test_epcis_captured_payload(self) -> None:
        payload = {
            "event": "EPCIS_CAPTURED",
            "dpp_id": str(uuid4()),
            "capture_id": "urn:uuid:test-capture",
            "event_count": 3,
        }
        compact = json.dumps(payload, separators=(",", ":"))
        assert '"event_count":3' in compact

    def test_dpp_exported_payload(self) -> None:
        payload = {
            "event": "DPP_EXPORTED",
            "dpp_id": str(uuid4()),
            "format": "aasx",
        }
        assert payload["format"] == "aasx"
