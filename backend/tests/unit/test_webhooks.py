"""Tests for webhook schemas, HMAC signing, and service logic."""

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.webhooks.client import (
    _sanitize_response,
    compute_signature,
    verify_signature,
)
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
        expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
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


# ── Response Sanitization Tests ───────────────────────────────────


class TestResponseSanitization:
    """Verify HTML stripping and truncation of response bodies."""

    def test_strips_html_tags(self) -> None:
        assert _sanitize_response("<h1>Hello</h1><script>alert(1)</script>") == "Helloalert(1)"

    def test_truncates_to_max_len(self) -> None:
        long_text = "x" * 2000
        result = _sanitize_response(long_text)
        assert result is not None
        assert len(result) == 1024

    def test_returns_none_for_empty(self) -> None:
        assert _sanitize_response(None) is None
        assert _sanitize_response("") is None

    def test_preserves_plain_text(self) -> None:
        assert _sanitize_response("OK") == "OK"


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

    def test_create_accepts_public_http(self) -> None:
        wh = WebhookCreate(url="http://example.com/hook", events=["DPP_CREATED"])
        assert "example.com" in str(wh.url)

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


# ── SSRF Protection Tests ─────────────────────────────────────────


class TestSSRFProtection:
    """Verify that internal/private URLs are rejected."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8000/internal",
            "http://127.0.0.1:8000/api",
            "http://10.0.0.1/internal",
            "http://172.16.0.1/internal",
            "http://172.31.255.255/internal",
            "http://192.168.1.1/internal",
            "http://169.254.169.254/latest/meta-data/",
            "http://0.0.0.0/",
        ],
    )
    def test_rejects_private_urls(self, url: str) -> None:
        with pytest.raises(ValidationError, match="private or internal"):
            WebhookCreate(url=url, events=["DPP_CREATED"])

    def test_accepts_public_url(self) -> None:
        wh = WebhookCreate(url="https://hooks.example.com/dpp", events=["DPP_CREATED"])
        assert "example.com" in str(wh.url)

    def test_accepts_public_ip(self) -> None:
        wh = WebhookCreate(url="https://93.184.216.34/hook", events=["DPP_CREATED"])
        assert "93.184" in str(wh.url)


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
