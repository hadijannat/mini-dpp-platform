"""EPCIS event emitter — creates EPCIS events from OPC UA triggers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("opcua_agent.epcis")


def build_epcis_event_payload(
    *,
    event_type: str,
    biz_step: str | None = None,
    disposition: str | None = None,
    action: str = "OBSERVE",
    read_point: str | None = None,
    biz_location: str | None = None,
    epc_list: list[str] | None = None,
    event_time: datetime | None = None,
    source_event_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal EPCIS event dict following GS1 EPCIS 2.0 JSON-LD."""
    now = event_time or datetime.now(tz=UTC)
    event: dict[str, Any] = {
        "type": event_type,
        "eventTime": now.isoformat(),
        "eventTimeZoneOffset": "+00:00",
        "action": action,
    }
    if biz_step:
        event["bizStep"] = biz_step
    if disposition:
        event["disposition"] = disposition
    if read_point:
        event["readPoint"] = {"id": read_point}
    if biz_location:
        event["bizLocation"] = {"id": biz_location}
    if epc_list:
        event["epcList"] = list(epc_list)
    if source_event_id:
        event["sourceEventId"] = source_event_id
    return event
