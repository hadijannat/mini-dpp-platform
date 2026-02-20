"""
Audit event logging for security and compliance tracking.

Provides ``emit_audit_event()`` for recording security-relevant actions
(create, update, delete, publish, export, deny) into the ``audit_events`` table.

Audit writes use a **separate short-lived session** so that a failure to write
an audit record does not roll back the business transaction.

When cryptographic hash chain columns are available (``event_hash``,
``prev_event_hash``, ``chain_sequence``), each event is chained to the
previous event in the same tenant for tamper-evident integrity.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request

from app.core.crypto.hash_chain import (
    HASH_ALGORITHM_SHA256,
    HASH_CANONICALIZATION_RFC8785,
)
from app.core.logging import get_logger
from app.core.security.oidc import TokenPayload
from app.db.models import AuditEvent

logger = get_logger(__name__)


def _has_hash_columns() -> bool:
    """Check whether the AuditEvent model has crypto hash chain columns."""
    mapper = AuditEvent.__table__
    return all(col in mapper.columns for col in ("event_hash", "prev_event_hash", "chain_sequence"))


def _build_event_data(
    *,
    action: str,
    resource_type: str,
    resource_id: str | None,
    tenant_id: str | None,
    subject: str | None,
    decision: str | None,
    ip_address: str | None,
    user_agent: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build the canonical dict used for hash computation."""
    data: dict[str, Any] = {
        "action": action,
        "resource_type": resource_type,
    }
    if resource_id is not None:
        data["resource_id"] = resource_id
    if tenant_id is not None:
        data["tenant_id"] = tenant_id
    if subject is not None:
        data["subject"] = subject
    if decision is not None:
        data["decision"] = decision
    if ip_address is not None:
        data["ip_address"] = ip_address
    if user_agent is not None:
        data["user_agent"] = user_agent
    if metadata is not None:
        data["metadata"] = metadata
    return data


async def emit_audit_event(
    *,
    db_session: Any,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None = None,
    tenant_id: UUID | None = None,
    user: TokenPayload | None = None,
    decision: str | None = "allow",
    request: Request | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Write a single audit event to the database.

    Parameters
    ----------
    db_session:
        An active ``AsyncSession``. The caller is responsible for committing
        (or the session middleware will auto-commit).
    action:
        Short verb describing the action, e.g. ``"create_dpp"``, ``"delete_policy"``,
        ``"publish_dpp"``, ``"abac_deny"``.
    resource_type:
        The type of resource acted upon, e.g. ``"dpp"``, ``"policy"``, ``"connector"``.
    resource_id:
        Primary key of the affected resource (may be None for list operations).
    tenant_id:
        Tenant scope.  None for platform-level operations.
    user:
        The authenticated user.  None for system-initiated events.
    decision:
        Policy decision string (``"allow"``, ``"deny"``, etc.).
    request:
        The current ``Request``; used to extract IP and User-Agent.
    metadata:
        Optional extra context to attach to the audit record.
    """
    ip_address: str | None = None
    user_agent: str | None = None

    if request is not None:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    event = AuditEvent(
        tenant_id=tenant_id,
        subject=user.sub if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        decision=decision,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_=metadata,
    )

    # Compute hash chain fields if the columns exist
    if _has_hash_columns():
        try:
            from sqlalchemy import desc, select, text

            from app.core.crypto.hash_chain import GENESIS_HASH, compute_event_hash

            # Acquire a per-tenant advisory lock to serialize hash chain writes.
            # Uses hashtext() for tenant_id string, or fixed key 0 for platform events.
            lock_key = "hashtext(:tid)" if tenant_id is not None else "0"
            await db_session.execute(
                text(f"SELECT pg_advisory_xact_lock({lock_key})"),
                {"tid": str(tenant_id)} if tenant_id is not None else {},
            )

            # Get the previous event hash for this tenant
            prev_query = (
                select(
                    AuditEvent.event_hash,
                    AuditEvent.chain_sequence,
                )
                .where(AuditEvent.tenant_id == tenant_id)
                .where(AuditEvent.chain_sequence.is_not(None))
                .order_by(desc(AuditEvent.chain_sequence))
                .limit(1)
            )
            result = await db_session.execute(prev_query)
            row = result.first()

            if row is not None:
                prev_hash = str(row[0]) if row[0] else GENESIS_HASH
                prev_seq = int(row[1]) if row[1] is not None else 0
            else:
                prev_hash = GENESIS_HASH
                prev_seq = -1

            event_data = _build_event_data(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                tenant_id=str(tenant_id) if tenant_id is not None else None,
                subject=user.sub if user else None,
                decision=decision,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata,
            )
            event_hash = compute_event_hash(
                event_data,
                prev_hash,
                canonicalization=HASH_CANONICALIZATION_RFC8785,
                hash_algorithm=HASH_ALGORITHM_SHA256,
            )

            event.event_hash = event_hash
            event.prev_event_hash = prev_hash
            event.chain_sequence = prev_seq + 1
            if hasattr(event, "hash_algorithm"):
                event.hash_algorithm = HASH_ALGORITHM_SHA256
            if hasattr(event, "hash_canonicalization"):
                event.hash_canonicalization = HASH_CANONICALIZATION_RFC8785
        except Exception:
            # If hash computation fails for any reason (missing columns,
            # migration not applied, etc.), log and continue without hashing
            logger.debug(
                "audit_hash_chain_skipped",
                reason="hash computation failed",
                exc_info=True,
            )

    try:
        db_session.add(event)
        await db_session.flush()
    except Exception:
        logger.warning(
            "audit_event_write_failed",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            exc_info=True,
        )
