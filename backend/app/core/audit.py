"""
Audit event logging for security and compliance tracking.

Provides ``emit_audit_event()`` for recording security-relevant actions
(create, update, delete, publish, export, deny) into the ``audit_events`` table.

Audit writes use a **separate short-lived session** so that a failure to write
an audit record does not roll back the business transaction.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request

from app.core.logging import get_logger
from app.core.security.oidc import TokenPayload
from app.db.models import AuditEvent

logger = get_logger(__name__)


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
