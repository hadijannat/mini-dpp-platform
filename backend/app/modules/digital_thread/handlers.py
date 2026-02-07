"""Auto-emission helpers for digital thread lifecycle events.

Maps common DPP actions (create, update, publish, archive) to lifecycle
phases and event types so that callers can fire-and-forget without knowing
the digital thread schema.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import LifecyclePhase

from .schemas import ThreadEventCreate
from .service import ThreadService

logger = get_logger(__name__)

# Maps DPP lifecycle actions to (phase, event_type) tuples
DEFAULT_ACTION_PHASE_MAP: dict[str, tuple[LifecyclePhase, str]] = {
    "create": (LifecyclePhase.DESIGN, "dpp_created"),
    "update": (LifecyclePhase.DESIGN, "dpp_updated"),
    "publish": (LifecyclePhase.DEPLOY, "dpp_published"),
    "archive": (LifecyclePhase.END_OF_LIFE, "dpp_archived"),
}


async def record_lifecycle_event(
    session: AsyncSession,
    dpp_id: UUID,
    tenant_id: UUID,
    action: str,
    created_by: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Record a digital thread event for a DPP lifecycle action.

    Looks up the action in ``DEFAULT_ACTION_PHASE_MAP`` and records the
    event via ``ThreadService``. Does nothing if:
    - ``digital_thread_enabled`` is ``False``
    - The action is not in the map

    This function swallows all exceptions so callers never fail due to
    digital thread recording issues.
    """
    settings = get_settings()
    if not settings.digital_thread_enabled:
        return

    mapping = DEFAULT_ACTION_PHASE_MAP.get(action)
    if mapping is None:
        return

    phase, event_type = mapping

    try:
        service = ThreadService(session)
        event = ThreadEventCreate(
            phase=phase,
            event_type=event_type,
            source="platform",
            payload=payload or {},
        )
        await service.record_event(dpp_id, tenant_id, event, created_by)
    except Exception:
        logger.warning(
            "digital_thread_auto_record_failed",
            dpp_id=str(dpp_id),
            action=action,
            exc_info=True,
        )
