"""Batch flush engine -- coalesced buffer -> DPP revisions."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DPP, DPPRevision
from app.modules.dpps.canonical_patch import apply_canonical_patch
from app.opcua_agent.deadletter import record_dead_letter
from app.opcua_agent.ingestion_buffer import BufferEntry, IngestionBuffer

logger = logging.getLogger("opcua_agent.flush")


@dataclass(frozen=True)
class FlushOutcome:
    """Outcome for flushing one DPP group."""

    status: Literal["ok", "retry", "deadletter"]
    reason: str | None = None


def _group_entries_by_dpp(
    entries: list[BufferEntry],
) -> dict[tuple[UUID, UUID], list[BufferEntry]]:
    """Group buffer entries by their (tenant_id, dpp_id) composite key."""
    grouped: dict[tuple[UUID, UUID], list[BufferEntry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.tenant_id, entry.dpp_id)].append(entry)
    return dict(grouped)


def _build_patch_operations(entries: list[BufferEntry]) -> list[dict[str, Any]]:
    """Build per-submodel patch operation lists from buffer entries.

    Groups entries by ``target_submodel_id`` and produces one patch dict
    per submodel with ``set_value`` operations for each entry.
    """
    by_submodel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_submodel[entry.target_submodel_id].append(
            {
                "op": "set_value",
                "path": entry.target_aas_path,
                "value": entry.value,
            }
        )
    return [{"submodel_id": sm_id, "operations": ops} for sm_id, ops in by_submodel.items()]


async def flush_buffer(
    buffer: IngestionBuffer,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Drain the buffer and flush all pending entries to DPP revisions.

    Returns the number of successfully flushed DPP groups.
    """
    entries = await buffer.drain()
    if not entries:
        return 0

    grouped = _group_entries_by_dpp(entries)
    success_count = 0
    retry_entries: list[BufferEntry] = []

    for (tenant_id, dpp_id), group_entries in grouped.items():
        try:
            async with session_factory() as session, session.begin():
                outcome = await _flush_single_dpp(
                    session=session,
                    tenant_id=tenant_id,
                    dpp_id=dpp_id,
                    entries=group_entries,
                )
                if outcome.status == "ok":
                    success_count += 1
                elif outcome.status == "retry":
                    retry_entries.extend(group_entries)
                elif outcome.status == "deadletter":
                    async with session_factory() as dl_session, dl_session.begin():
                        for entry in group_entries:
                            await record_dead_letter(
                                session=dl_session,
                                tenant_id=tenant_id,
                                mapping_id=entry.mapping_id,
                                value_payload={
                                    "value": entry.value,
                                    "path": entry.target_aas_path,
                                    "submodel_id": entry.target_submodel_id,
                                },
                                error=outcome.reason or f"Flush failed for DPP {dpp_id}",
                            )
        except Exception:
            logger.exception("Failed to flush DPP %s for tenant %s", dpp_id, tenant_id)
            # Record dead letters for each entry in the failed group
            try:
                async with session_factory() as dl_session, dl_session.begin():
                    for entry in group_entries:
                        await record_dead_letter(
                            session=dl_session,
                            tenant_id=tenant_id,
                            mapping_id=entry.mapping_id,
                            value_payload={
                                "value": entry.value,
                                "path": entry.target_aas_path,
                                "submodel_id": entry.target_submodel_id,
                            },
                            error=f"Flush failed for DPP {dpp_id}",
                        )
            except Exception:
                logger.exception("Failed to record dead letters for DPP %s", dpp_id)

    if retry_entries:
        await buffer.put_entries(retry_entries)
        logger.info("Requeued %d buffered entries for retry", len(retry_entries))

    logger.info(
        "Flush complete: %d/%d DPP groups succeeded (requeued=%d)",
        success_count,
        len(grouped),
        len(retry_entries),
    )
    return success_count


async def _flush_single_dpp(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    dpp_id: UUID,
    entries: list[BufferEntry],
) -> FlushOutcome:
    """Flush entries for a single DPP within an existing transaction.

    Uses a PostgreSQL advisory lock to prevent concurrent flushes for the
    same DPP.
    """
    lock_key = f"opcua_flush:{tenant_id}:{dpp_id}"
    lock_result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
        {"key": lock_key},
    )
    got_lock = lock_result.scalar()
    if not got_lock:
        logger.warning(
            "Could not acquire advisory lock for DPP %s — skipping flush",
            dpp_id,
        )
        return FlushOutcome(status="retry", reason=f"Advisory lock unavailable for DPP {dpp_id}")

    # Load the DPP
    dpp = await session.get(DPP, dpp_id)
    if dpp is None:
        logger.warning("DPP %s not found — skipping flush", dpp_id)
        return FlushOutcome(status="deadletter", reason=f"DPP {dpp_id} not found")

    # Load the latest revision
    latest_rev_stmt = (
        select(DPPRevision)
        .where(DPPRevision.dpp_id == dpp_id)
        .order_by(DPPRevision.revision_no.desc())
        .limit(1)
    )
    latest_rev = (await session.scalars(latest_rev_stmt)).first()
    if latest_rev is None:
        logger.warning("DPP %s has no revisions — skipping flush", dpp_id)
        return FlushOutcome(
            status="deadletter",
            reason=f"DPP {dpp_id} has no revisions available for patching",
        )

    # Build and apply patches
    patches = _build_patch_operations(entries)
    current_env = latest_rev.aas_env_json

    for patch in patches:
        result = apply_canonical_patch(
            aas_env_json=current_env,
            submodel_id=patch["submodel_id"],
            operations=patch["operations"],
            contract=None,
            strict=False,
        )
        current_env = result.aas_env_json

    # Compute digest
    canonical = json.dumps(current_env, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()

    # Create new revision
    new_revision_no = (latest_rev.revision_no or 0) + 1
    new_rev = DPPRevision(
        tenant_id=tenant_id,
        dpp_id=dpp_id,
        revision_no=new_revision_no,
        state=latest_rev.state,
        aas_env_json=current_env,
        digest_sha256=digest,
        created_by_subject="opcua-agent",
        template_provenance=latest_rev.template_provenance or {},
    )
    session.add(new_rev)
    await session.flush()

    logger.info(
        "Flushed DPP %s: revision %d -> %d (%d entries)",
        dpp_id,
        latest_rev.revision_no,
        new_revision_no,
        len(entries),
    )
    return FlushOutcome(status="ok")
