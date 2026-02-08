"""GS1 structural validation for EPCIS 2.0 events.

Programmatic validation of EPCIS events against GS1 normative structural
rules. This does not download external JSON schemas — it implements key
rules directly for offline, deterministic validation.

Gated by the ``epcis_validate_gs1_schema`` config setting.
"""

from __future__ import annotations

import re
from typing import Any

# Valid action values per GS1 EPCIS 2.0
_VALID_ACTIONS = {"ADD", "OBSERVE", "DELETE"}

# Event types that MUST have an action field
_ACTION_REQUIRED_TYPES = {
    "ObjectEvent",
    "AggregationEvent",
    "TransactionEvent",
    "AssociationEvent",
}

# Event types that MUST NOT have an action field
_ACTION_FORBIDDEN_TYPES = {"TransformationEvent"}

# Fields always required on every event
_ALWAYS_REQUIRED = {"eventTime", "eventTimeZoneOffset", "type"}

# EPC URI prefix pattern (urn:epc:id:... or urn:epc:class:...)
_EPC_URN_RE = re.compile(r"^urn:epc:(id|class|idpat):")

# ISO 8601 timezone offset pattern (+HH:MM or -HH:MM or Z)
_TZ_OFFSET_RE = re.compile(r"^[+-]\d{2}:\d{2}$|^Z$")


def validate_against_gs1_schema(event_data: dict[str, Any]) -> list[str]:
    """Validate an EPCIS event dict against GS1 structural rules.

    Returns a list of validation error strings. An empty list means valid.

    Args:
        event_data: Dict representation of an EPCIS event (camelCase keys).

    Returns:
        List of error message strings (empty = valid).
    """
    errors: list[str] = []

    # 1. Check always-required fields
    for field in _ALWAYS_REQUIRED:
        if field not in event_data or event_data[field] is None:
            errors.append(f"Missing required field: {field}")

    event_type = event_data.get("type")

    # 2. Validate eventTimeZoneOffset format
    tz_offset = event_data.get("eventTimeZoneOffset")
    if tz_offset is not None and not _TZ_OFFSET_RE.match(str(tz_offset)):
        errors.append(
            f"Invalid eventTimeZoneOffset format: {tz_offset!r} (expected +HH:MM, -HH:MM, or Z)"
        )

    # 3. Validate action field presence and value
    action = event_data.get("action")

    if event_type in _ACTION_REQUIRED_TYPES:
        if action is None:
            errors.append(f"{event_type} requires an 'action' field")
        elif action not in _VALID_ACTIONS:
            errors.append(
                f"Invalid action value: {action!r} "
                f"(must be one of {', '.join(sorted(_VALID_ACTIONS))})"
            )

    if event_type in _ACTION_FORBIDDEN_TYPES and action is not None:
        errors.append(f"{event_type} must NOT have an 'action' field")

    # 4. Type-specific required field checks
    if event_type == "TransactionEvent":
        biz_list = event_data.get("bizTransactionList")
        if not biz_list:
            errors.append("TransactionEvent requires a non-empty 'bizTransactionList'")

    # 5. Warn on non-standard EPC URIs (soft check — warnings, not errors)
    _check_epc_uris(event_data, errors)

    return errors


def _check_epc_uris(event_data: dict[str, Any], errors: list[str]) -> None:
    """Check EPC URIs match expected urn:epc: prefix (warning-level)."""
    epc_list_keys = [
        "epcList",
        "childEPCs",
        "inputEPCList",
        "outputEPCList",
    ]

    for key in epc_list_keys:
        epcs = event_data.get(key)
        if not isinstance(epcs, list):
            continue
        for epc in epcs:
            if isinstance(epc, str) and not _EPC_URN_RE.match(epc):
                errors.append(
                    f"EPC URI '{epc}' in '{key}' does not match expected "
                    f"'urn:epc:' prefix pattern (warning)"
                )

    # Check parentID if present
    parent_id = event_data.get("parentID")
    if isinstance(parent_id, str) and parent_id and not _EPC_URN_RE.match(parent_id):
        errors.append(
            f"parentID '{parent_id}' does not match expected 'urn:epc:' prefix pattern (warning)"
        )
