"""HTTP client for webhook delivery with HMAC-SHA256 signing."""

import hashlib
import hmac
import json
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Persistent HTTP client — lazily initialized, reuses connections
_http_client: httpx.AsyncClient | None = None

# Strip HTML tags from response body to prevent stored XSS
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        settings = get_settings()
        _http_client = httpx.AsyncClient(
            timeout=settings.webhook_timeout_seconds,
            follow_redirects=False,
        )
    return _http_client


def compute_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for a webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload_bytes: bytes, secret: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = compute_signature(payload_bytes, secret)
    return hmac.compare_digest(expected, signature)


def _sanitize_response(text: str | None, max_len: int = 1024) -> str | None:
    """Strip HTML tags and truncate response body for safe storage."""
    if not text:
        return None
    cleaned = _HTML_TAG_RE.sub("", text)
    return cleaned[:max_len]


async def deliver_webhook(
    url: str,
    payload: dict[str, Any],
    secret: str,
) -> tuple[int | None, str | None, str | None]:
    """
    Deliver a webhook payload to the given URL.

    Returns:
        Tuple of (http_status, response_body_truncated, error_message).
        On connection failure, http_status is None.
    """
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = compute_signature(payload_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-DPP-Signature-256": f"sha256={signature}",
        "User-Agent": "DPP-Platform-Webhook/1.0",
    }

    try:
        client = _get_http_client()
        response = await client.post(url, content=payload_bytes, headers=headers)
        body = _sanitize_response(response.text)
        return response.status_code, body, None
    except httpx.TimeoutException:
        return None, None, "Connection timed out"
    except httpx.ConnectError as exc:
        return None, None, f"Connection failed: {exc}"
    except Exception as exc:
        logger.warning("webhook_delivery_error", url=url, exc_info=True)
        return None, None, str(exc)
