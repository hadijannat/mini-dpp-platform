"""Timeline projections for the digital thread.

Provides pre-filtered views of the event timeline:
- Full lifecycle timeline ordered by phase
- Compliance-relevant timeline for regulatory evidence
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LifecyclePhase, ThreadEvent

from .schemas import LifecycleTimeline, ThreadEventResponse

# Canonical lifecycle phase ordering
_PHASE_ORDER: list[LifecyclePhase] = [
    LifecyclePhase.DESIGN,
    LifecyclePhase.MANUFACTURE,
    LifecyclePhase.LOGISTICS,
    LifecyclePhase.DEPLOY,
    LifecyclePhase.OPERATE,
    LifecyclePhase.MAINTAIN,
    LifecyclePhase.END_OF_LIFE,
]

# Phases relevant to regulatory compliance evidence
_COMPLIANCE_PHASES: set[LifecyclePhase] = {
    LifecyclePhase.MANUFACTURE,
    LifecyclePhase.DEPLOY,
    LifecyclePhase.END_OF_LIFE,
}

# Event type keywords that indicate compliance-relevant events
_COMPLIANCE_KEYWORDS: tuple[str, ...] = (
    "compliance",
    "certification",
    "inspection",
    "test",
    "audit",
)


async def get_lifecycle_timeline(
    session: AsyncSession,
    dpp_id: UUID,
    tenant_id: UUID,
) -> LifecycleTimeline:
    """Get all events grouped by phase in canonical lifecycle order.

    Phases appear in the order defined by ``_PHASE_ORDER`` rather than
    insertion order, making the output deterministic and semantically
    meaningful.
    """
    stmt = (
        select(ThreadEvent)
        .where(
            ThreadEvent.dpp_id == dpp_id,
            ThreadEvent.tenant_id == tenant_id,
        )
        .order_by(ThreadEvent.created_at)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Group by phase in canonical order
    phases: dict[str, list[ThreadEventResponse]] = {}
    for phase in _PHASE_ORDER:
        phase_events = [ThreadEventResponse.model_validate(r) for r in rows if r.phase == phase]
        if phase_events:
            phases[phase.value] = phase_events

    return LifecycleTimeline(dpp_id=dpp_id, phases=phases, total_events=len(rows))


async def get_compliance_timeline(
    session: AsyncSession,
    dpp_id: UUID,
    tenant_id: UUID,
) -> LifecycleTimeline:
    """Get only compliance-relevant events for regulatory evidence.

    Filters events to:
    - Phases: MANUFACTURE, DEPLOY, END_OF_LIFE
    - Event types containing keywords: compliance, certification,
      inspection, test, audit
    """
    stmt = (
        select(ThreadEvent)
        .where(
            ThreadEvent.dpp_id == dpp_id,
            ThreadEvent.tenant_id == tenant_id,
            ThreadEvent.phase.in_(_COMPLIANCE_PHASES),
        )
        .order_by(ThreadEvent.created_at)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Further filter by event_type keywords
    filtered = [r for r in rows if any(kw in r.event_type.lower() for kw in _COMPLIANCE_KEYWORDS)]

    phases: dict[str, list[ThreadEventResponse]] = {}
    for phase in _PHASE_ORDER:
        phase_events = [ThreadEventResponse.model_validate(r) for r in filtered if r.phase == phase]
        if phase_events:
            phases[phase.value] = phase_events

    return LifecycleTimeline(
        dpp_id=dpp_id,
        phases=phases,
        total_events=len(filtered),
    )
