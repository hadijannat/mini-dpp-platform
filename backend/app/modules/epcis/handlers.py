"""Auto-emission helpers for EPCIS lifecycle events.

Maps common DPP actions (create, publish, archive) to EPCIS ObjectEvents
so that callers can fire-and-forget without knowing the EPCIS schema.

Mirrors the pattern in ``digital_thread.handlers``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import EPCISEvent, EPCISEventType

logger = get_logger(__name__)

# Maps DPP lifecycle actions to (biz_step, disposition) tuples.
# All auto-emitted events are ObjectEvents.
DEFAULT_ACTION_EPCIS_MAP: dict[str, tuple[str, str, str]] = {
    # action -> (epcis_action, biz_step, disposition)
    "create": ("ADD", "commissioning", "active"),
    "publish": ("OBSERVE", "inspecting", "conformant"),
    "archive": ("DELETE", "decommissioning", "inactive"),
}


async def record_epcis_lifecycle_event(
    session: AsyncSession,
    dpp_id: UUID,
    tenant_id: UUID,
    action: str,
    created_by: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record an EPCIS ObjectEvent for a DPP lifecycle action.

    Looks up the action in ``DEFAULT_ACTION_EPCIS_MAP`` and records the
    event. Does nothing if:
    - ``epcis_enabled`` is ``False``
    - ``epcis_auto_record`` is ``False``
    - The action is not in the map

    This function swallows all exceptions so callers never fail due to
    EPCIS recording issues.
    """
    settings = get_settings()
    if not settings.epcis_enabled or not settings.epcis_auto_record:
        return

    mapping = DEFAULT_ACTION_EPCIS_MAP.get(action)
    if mapping is None:
        return

    epcis_action, biz_step, disposition = mapping

    try:
        async with session.begin_nested():
            now = datetime.now(tz=UTC)
            event = EPCISEvent(
                tenant_id=tenant_id,
                dpp_id=dpp_id,
                event_id=f"urn:uuid:{uuid.uuid4()}",
                event_type=EPCISEventType.OBJECT,
                event_time=now,
                event_time_zone_offset="+00:00",
                action=epcis_action,
                biz_step=biz_step,
                disposition=disposition,
                payload=payload or {},
                created_by_subject=created_by,
            )
            session.add(event)
    except Exception:
        logger.warning(
            "epcis_auto_record_failed",
            dpp_id=str(dpp_id),
            action=action,
            exc_info=True,
        )
