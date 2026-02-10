"""
CRUD service for role upgrade requests.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import emit_audit_event
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.logging import get_logger
from app.core.security.oidc import TokenPayload
from app.db.models import (
    RoleRequestStatus,
    RoleUpgradeRequest,
    TenantMember,
    TenantRole,
)

logger = get_logger(__name__)


class RoleRequestService:
    """Manages role upgrade request lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_request(
        self,
        *,
        tenant_id: UUID,
        user: TokenPayload,
        requested_role: str,
        reason: str | None = None,
    ) -> RoleUpgradeRequest:
        """Create a new PENDING role upgrade request."""
        # Validate requested role
        try:
            role = TenantRole(requested_role)
        except ValueError:
            raise ValueError(f"Invalid role: {requested_role}")

        if role == TenantRole.VIEWER:
            raise ValueError("Cannot request viewer role — it is the default")

        if role == TenantRole.TENANT_ADMIN:
            raise ValueError("Cannot self-request tenant_admin role")

        # Check for existing pending request
        existing = await self._db.execute(
            select(RoleUpgradeRequest).where(
                RoleUpgradeRequest.tenant_id == tenant_id,
                RoleUpgradeRequest.user_subject == user.sub,
                RoleUpgradeRequest.status == RoleRequestStatus.PENDING,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("A pending role request already exists")

        request = RoleUpgradeRequest(
            tenant_id=tenant_id,
            user_subject=user.sub,
            requested_role=role,
            status=RoleRequestStatus.PENDING,
            reason=reason,
        )
        self._db.add(request)
        await self._db.flush()

        await emit_audit_event(
            db_session=self._db,
            action="role_upgrade_requested",
            resource_type="role_upgrade_request",
            resource_id=str(request.id),
            user=user,
            tenant_id=tenant_id,
            metadata={"requested_role": requested_role},
        )

        logger.info(
            "role_upgrade_requested",
            sub=user.sub,
            requested_role=requested_role,
        )
        return request

    async def list_requests(
        self,
        tenant_id: UUID,
        status_filter: RoleRequestStatus | None = None,
    ) -> list[RoleUpgradeRequest]:
        """List role upgrade requests for a tenant (admin view)."""
        stmt = select(RoleUpgradeRequest).where(RoleUpgradeRequest.tenant_id == tenant_id)
        if status_filter:
            stmt = stmt.where(RoleUpgradeRequest.status == status_filter)
        stmt = stmt.order_by(RoleUpgradeRequest.created_at.desc())
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_requests(
        self,
        tenant_id: UUID,
        user_subject: str,
    ) -> list[RoleUpgradeRequest]:
        """List a user's own role requests."""
        result = await self._db.execute(
            select(RoleUpgradeRequest)
            .where(
                RoleUpgradeRequest.tenant_id == tenant_id,
                RoleUpgradeRequest.user_subject == user_subject,
            )
            .order_by(RoleUpgradeRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def review_request(
        self,
        *,
        request_id: UUID,
        tenant_id: UUID,
        approved: bool,
        reviewer: TokenPayload,
        review_note: str | None = None,
    ) -> RoleUpgradeRequest:
        """Approve or deny a role upgrade request."""
        result = await self._db.execute(
            select(RoleUpgradeRequest).where(
                RoleUpgradeRequest.id == request_id,
                RoleUpgradeRequest.tenant_id == tenant_id,
            )
        )
        request = result.scalar_one_or_none()
        if not request:
            raise ValueError("Role request not found")

        if request.status != RoleRequestStatus.PENDING:
            raise ValueError(f"Request already {request.status.value}")

        request.status = RoleRequestStatus.APPROVED if approved else RoleRequestStatus.DENIED
        request.reviewed_by = reviewer.sub
        request.review_note = review_note
        request.reviewed_at = datetime.now(UTC)

        if approved:
            # Update tenant membership role
            membership_result = await self._db.execute(
                select(TenantMember).where(
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.user_subject == request.user_subject,
                )
            )
            membership = membership_result.scalar_one_or_none()
            if membership:
                membership.role = request.requested_role

            # Best-effort Keycloak sync
            try:
                kc = KeycloakAdminClient()
                await kc.assign_realm_role(request.user_subject, request.requested_role.value)
            except Exception:
                logger.exception(
                    "keycloak_sync_failed_on_approval",
                    user=request.user_subject,
                    role=request.requested_role.value,
                )

        await self._db.flush()

        action = "role_upgrade_approved" if approved else "role_upgrade_denied"
        await emit_audit_event(
            db_session=self._db,
            action=action,
            resource_type="role_upgrade_request",
            resource_id=str(request.id),
            user=reviewer,
            tenant_id=tenant_id,
            metadata={
                "target_user": request.user_subject,
                "requested_role": request.requested_role.value,
            },
        )

        return request
