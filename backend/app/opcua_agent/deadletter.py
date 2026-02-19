"""Dead letter recorder for failed OPC UA → DPP mapping operations.

Upserts a row in ``opcua_deadletters``: if a record already exists for
the given (tenant_id, mapping_id) pair, increments its count and updates
error / payload / timestamp.  Otherwise creates a new row with count=1.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OPCUADeadLetter

logger = logging.getLogger(__name__)


async def record_dead_letter(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    mapping_id: UUID,
    value_payload: dict[str, Any] | None,
    error: str,
) -> None:
    """Record or update a dead letter entry for a failed mapping.

    Args:
        session: Active async database session (caller manages transaction).
        tenant_id: Tenant that owns the mapping.
        mapping_id: The OPC UA mapping that failed.
        value_payload: The OPC UA value that could not be applied (may be None).
        error: Human-readable error description.
    """
    stmt = select(OPCUADeadLetter).where(
        OPCUADeadLetter.tenant_id == tenant_id,
        OPCUADeadLetter.mapping_id == mapping_id,
    )
    result = await session.scalars(stmt)
    existing = result.first()

    if existing is not None:
        existing.count += 1
        existing.error = error
        existing.value_payload = value_payload
        existing.last_seen_at = datetime.now(UTC)
        logger.debug(
            "Dead letter updated: mapping=%s count=%d",
            mapping_id,
            existing.count,
        )
    else:
        now = datetime.now(UTC)
        entry = OPCUADeadLetter(
            tenant_id=tenant_id,
            mapping_id=mapping_id,
            value_payload=value_payload,
            error=error,
            count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add(entry)
        logger.info("Dead letter created: mapping=%s error=%s", mapping_id, error)

    await session.flush()
