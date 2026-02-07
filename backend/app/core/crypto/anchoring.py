"""
RFC 3161 Timestamp Authority (TSA) client.

Provides optional external timestamping of Merkle roots for independent
proof of existence. Gracefully skips when no TSA URL is configured.
"""

from __future__ import annotations

import hashlib
import os

import httpx
from asn1crypto import algos, core, tsp  # type: ignore[import-untyped]

from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_ts_request(digest: bytes) -> bytes:
    """Build an RFC 3161 TimeStampReq ASN.1 structure.

    Parameters
    ----------
    digest:
        Raw SHA-256 digest bytes (32 bytes) to timestamp.

    Returns
    -------
    bytes
        DER-encoded TimeStampReq.
    """
    message_imprint = tsp.MessageImprint(
        {
            "hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
            "hashed_message": core.OctetString(digest),
        }
    )

    nonce = int.from_bytes(os.urandom(8))

    ts_request = tsp.TimeStampReq(
        {
            "version": 1,
            "message_imprint": message_imprint,
            "nonce": nonce,
            "cert_req": True,
        }
    )

    return bytes(ts_request.dump())


async def request_timestamp(digest: bytes, tsa_url: str) -> bytes | None:
    """Send a timestamp request to an RFC 3161 TSA.

    Parameters
    ----------
    digest:
        Raw SHA-256 digest bytes (32 bytes) to timestamp.
    tsa_url:
        URL of the RFC 3161 Timestamp Authority endpoint.

    Returns
    -------
    bytes | None
        DER-encoded TimeStampResp token, or ``None`` if the request fails.
    """
    if not tsa_url:
        logger.debug("tsa_skipped", reason="no TSA URL configured")
        return None

    ts_req = _build_ts_request(digest)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                tsa_url,
                content=ts_req,
                headers={"Content-Type": "application/timestamp-query"},
            )
            response.raise_for_status()

            ts_resp = tsp.TimeStampResp.load(response.content)
            status_value = ts_resp["status"]["status"].native
            if status_value != "granted":
                logger.warning(
                    "tsa_request_rejected",
                    status=status_value,
                    tsa_url=tsa_url,
                )
                return None

            return bytes(response.content)
    except Exception:
        logger.warning(
            "tsa_request_failed",
            tsa_url=tsa_url,
            exc_info=True,
        )
        return None


def verify_timestamp(token: bytes, digest: bytes) -> bool:
    """Verify that a TSA token covers the given digest.

    Checks that the embedded message imprint matches the expected digest.
    Does NOT verify the TSA's certificate chain (that would require a
    trust store configuration beyond this module's scope).

    Parameters
    ----------
    token:
        DER-encoded TimeStampResp bytes.
    digest:
        The original SHA-256 digest bytes that were timestamped.

    Returns
    -------
    bool
        ``True`` if the token's message imprint matches the digest.
    """
    try:
        ts_resp = tsp.TimeStampResp.load(token)
        tst_info = ts_resp["time_stamp_token"]["content"]["encap_content_info"]
        signed_data = tst_info["content"].parsed
        imprint = signed_data["message_imprint"]["hashed_message"].native
        return bool(imprint == digest)
    except Exception:
        logger.warning("tsa_verify_failed", exc_info=True)
        return False


def hash_for_timestamping(data: str) -> bytes:
    """Compute a SHA-256 digest suitable for TSA timestamping.

    Parameters
    ----------
    data:
        String data (typically a Merkle root hash) to digest.

    Returns
    -------
    bytes
        Raw 32-byte SHA-256 digest.
    """
    return hashlib.sha256(data.encode("utf-8")).digest()
