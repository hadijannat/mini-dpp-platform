"""Digital thread service — business logic for lifecycle event recording.

Provides ``ThreadService`` for recording and querying product lifecycle
events that form a DPP's digital thread.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DPP, ThreadEvent

from .schemas import (
    EventQuery,
    LifecycleTimeline,
    ThreadEventCreate,
    ThreadEventResponse,
)

logger = get_logger(__name__)


class ThreadService:
    """DPP-aware digital thread event service.

    Usage::

        service = ThreadService(db_session)
        event = await service.record_event(dpp_id, tenant_id, create, user_sub)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
        event: ThreadEventCreate,
        created_by: str,
    ) -> ThreadEventResponse:
        """Record a new digital thread event for a DPP.

        Validates that the DPP exists and belongs to the tenant, then
        inserts a ``ThreadEvent`` row.

        Raises:
            ValueError: If the DPP does not exist or is not in this tenant.
        """
        dpp = await self._get_dpp(dpp_id, tenant_id)
        if dpp is None:
            raise ValueError(f"DPP {dpp_id} not found")

        thread_event = ThreadEvent(
            dpp_id=dpp_id,
            tenant_id=tenant_id,
            phase=event.phase,
            event_type=event.event_type,
            source=event.source,
            source_event_id=event.source_event_id,
            payload=event.payload,
            parent_event_id=event.parent_event_id,
            created_by_subject=created_by,
        )
        self._session.add(thread_event)
        await self._session.flush()

        logger.info(
            "thread_event_recorded",
            dpp_id=str(dpp_id),
            phase=event.phase.value,
            event_type=event.event_type,
            source=event.source,
        )

        return ThreadEventResponse.model_validate(thread_event)

    async def get_events(
        self,
        tenant_id: UUID,
        query: EventQuery,
    ) -> list[ThreadEventResponse]:
        """Query thread events with optional filters."""
        stmt = (
            select(ThreadEvent)
            .where(
                ThreadEvent.dpp_id == query.dpp_id,
                ThreadEvent.tenant_id == tenant_id,
            )
            .order_by(ThreadEvent.created_at)
        )

        if query.phase is not None:
            stmt = stmt.where(ThreadEvent.phase == query.phase)

        if query.event_type is not None:
            stmt = stmt.where(ThreadEvent.event_type == query.event_type)

        stmt = stmt.limit(query.limit).offset(query.offset)

        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [ThreadEventResponse.model_validate(row) for row in rows]

    async def get_timeline(
        self,
        dpp_id: UUID,
        tenant_id: UUID,
    ) -> LifecycleTimeline:
        """Get all events for a DPP grouped by lifecycle phase."""
        stmt = (
            select(ThreadEvent)
            .where(
                ThreadEvent.dpp_id == dpp_id,
                ThreadEvent.tenant_id == tenant_id,
            )
            .order_by(ThreadEvent.created_at)
        )

        result = await self._session.execute(stmt)
        rows = result.scalars().all()

        phases: dict[str, list[ThreadEventResponse]] = {}
        for row in rows:
            phase_key = row.phase.value
            if phase_key not in phases:
                phases[phase_key] = []
            phases[phase_key].append(ThreadEventResponse.model_validate(row))

        count_result = await self._session.execute(
            select(func.count())
            .select_from(ThreadEvent)
            .where(
                ThreadEvent.dpp_id == dpp_id,
                ThreadEvent.tenant_id == tenant_id,
            )
        )
        total = count_result.scalar_one()

        return LifecycleTimeline(
            dpp_id=dpp_id,
            phases=phases,
            total_events=total,
        )

    async def _get_dpp(self, dpp_id: UUID, tenant_id: UUID) -> DPP | None:
        """Verify that a DPP exists and belongs to the tenant."""
        result = await self._session.execute(
            select(DPP).where(
                DPP.id == dpp_id,
                DPP.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()
