"""GS1 Digital Link URI utilities for EPCIS integration.

Provides builders and parsers for GS1 Digital Link URIs used as EPC
identifiers in EPCIS events. Coordinates with the existing QR module's
``QRCodeService.build_gs1_digital_link()`` for consistency.

Reference: https://www.gs1.org/standards/gs1-digital-link
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote

# Matches /01/{GTIN} with optional /21/{serial} and /10/{batch}
_DIGITAL_LINK_RE = re.compile(
    r"^(?P<resolver>https?://[^/]+)"
    r"/01/(?P<gtin>[0-9]+)"
    r"(?:/21/(?P<serial>[^/]+))?"
    r"(?:/10/(?P<batch>[^/]+))?"
    r"/?$"
)


def build_digital_link(
    gtin: str,
    serial: str | None = None,
    batch: str | None = None,
    resolver: str = "https://id.gs1.org",
) -> str:
    """Build a GS1 Digital Link URI from components.

    Args:
        gtin: Global Trade Item Number (digits only).
        serial: Serial number for instance-level identification.
        batch: Batch/lot number.
        resolver: GS1 resolver base URL.

    Returns:
        GS1 Digital Link URI string.
    """
    base = resolver.rstrip("/")
    clean_gtin = "".join(filter(str.isdigit, gtin))
    if not clean_gtin:
        raise ValueError("GTIN must contain at least one digit")

    uri = f"{base}/01/{quote(clean_gtin, safe='')}"

    if serial is not None:
        uri += f"/21/{quote(str(serial), safe='')}"

    if batch is not None:
        uri += f"/10/{quote(str(batch), safe='')}"

    return uri


def parse_digital_link(uri: str) -> dict[str, str]:
    """Parse a GS1 Digital Link URI into its components.

    Args:
        uri: A GS1 Digital Link URI.

    Returns:
        Dict with keys ``resolver``, ``gtin``, and optionally
        ``serial`` and ``batch``.

    Raises:
        ValueError: If the URI is not a valid GS1 Digital Link.
    """
    match = _DIGITAL_LINK_RE.match(uri)
    if not match:
        raise ValueError(f"Not a valid GS1 Digital Link URI: {uri}")

    result: dict[str, str] = {
        "resolver": match.group("resolver"),
        "gtin": unquote(match.group("gtin")),
    }

    serial = match.group("serial")
    if serial is not None:
        result["serial"] = unquote(serial)

    batch = match.group("batch")
    if batch is not None:
        result["batch"] = unquote(batch)

    return result


def is_digital_link(uri: str) -> bool:
    """Check whether a string is a valid GS1 Digital Link URI."""
    return _DIGITAL_LINK_RE.match(uri) is not None
