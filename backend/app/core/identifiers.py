"""
Identifier normalization and construction helpers.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse, urlunparse


class IdentifierValidationError(ValueError):
    """Raised when identifier inputs are invalid."""


def normalize_base_uri(base_uri: str) -> str:
    """
    Normalize and validate the global asset ID base URI.

    Requirements:
    - http scheme only
    - host required
    - no query or fragment
    - trailing slash required
    """
    if base_uri is None:
        raise IdentifierValidationError("Base URI is required.")

    raw = base_uri.strip()
    if not raw:
        raise IdentifierValidationError("Base URI cannot be empty.")

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()

    if scheme != "http":
        raise IdentifierValidationError("Base URI must use the http scheme.")
    if not parsed.netloc:
        raise IdentifierValidationError("Base URI must include a host.")
    if parsed.query or parsed.fragment:
        raise IdentifierValidationError("Base URI must not include query or fragment.")
    if parsed.params:
        raise IdentifierValidationError("Base URI must not include path parameters.")

    path = parsed.path or "/"
    if not path.endswith("/"):
        path = f"{path}/"

    normalized = parsed._replace(
        scheme=scheme,
        netloc=parsed.netloc.lower(),
        path=path,
        query="",
        fragment="",
        params="",
    )

    return urlunparse(normalized)


def build_composite_suffix(asset_ids: dict[str, Any]) -> str:
    """
    Build a composite identifier suffix from asset identifiers.

    Uses manufacturerPartId plus optional serialNumber and batchId.
    """
    manufacturer_part_id = str(asset_ids.get("manufacturerPartId", "")).strip()
    if not manufacturer_part_id:
        raise IdentifierValidationError(
            "manufacturerPartId is required to build globalAssetId."
        )

    parts: list[str] = [manufacturer_part_id]
    serial = str(asset_ids.get("serialNumber", "")).strip()
    batch = str(asset_ids.get("batchId", "")).strip()

    if serial:
        parts.append(serial)
    if batch:
        parts.append(batch)

    encoded_parts = [quote(part, safe="") for part in parts]
    return "--".join(encoded_parts)


def build_global_asset_id(base_uri: str, asset_ids: dict[str, Any]) -> str:
    """
    Build a global asset ID using the normalized base URI and composite suffix.
    """
    normalized_base = normalize_base_uri(base_uri)
    suffix = build_composite_suffix(asset_ids)
    return f"{normalized_base}{suffix}"
