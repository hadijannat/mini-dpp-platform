"""
CRUD service for role upgrade requests.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.logging import get_logger
from app.core.notifications import (
    EmailClient,
    build_role_request_decision_email,
    build_role_request_submitted_admin_email,
    build_role_request_submitted_requester_email,
)
from app.core.security.oidc import TokenPayload
from app.db.models import (
    RoleRequestStatus,
    RoleUpgradeRequest,
    Tenant,
    TenantMember,
    TenantRole,
    User,
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
        await self._safe_notify_request_created(
            request=request,
            requester_email=user.email,
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

    async def get_requester_identity_map(
        self,
        user_subjects: Iterable[str],
    ) -> dict[str, tuple[str | None, str | None]]:
        """Resolve requester contact/display details for UI rendering."""
        subjects = sorted({subject.strip() for subject in user_subjects if subject and subject.strip()})
        if not subjects:
            return {}

        result = await self._db.execute(
            select(User.subject, User.email, User.display_name).where(User.subject.in_(subjects))
        )
        identity_map: dict[str, tuple[str | None, str | None]] = {}
        for subject, email, display_name in result.all():
            if not isinstance(subject, str):
                continue
            identity_map[subject] = (
                email.strip() if isinstance(email, str) and email.strip() else None,
                display_name.strip() if isinstance(display_name, str) and display_name.strip() else None,
            )
        return identity_map

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

        await self._safe_notify_request_reviewed(
            request=request,
            approved=approved,
        )

        return request

    async def _safe_notify_request_created(
        self,
        *,
        request: RoleUpgradeRequest,
        requester_email: str | None,
    ) -> None:
        """Best-effort wrapper around submit notification delivery."""
        try:
            await self._notify_request_created(
                request=request,
                tenant_slug=await self._get_tenant_slug(request.tenant_id),
                requester_email=requester_email,
            )
        except Exception:
            logger.exception(
                "role_request_submit_notifications_failed",
                request_id=str(request.id),
                tenant_id=str(request.tenant_id),
            )

    async def _safe_notify_request_reviewed(
        self,
        *,
        request: RoleUpgradeRequest,
        approved: bool,
    ) -> None:
        """Best-effort wrapper around decision notification delivery."""
        try:
            await self._notify_request_reviewed(
                request=request,
                tenant_slug=await self._get_tenant_slug(request.tenant_id),
                approved=approved,
            )
        except Exception:
            logger.exception(
                "role_request_decision_notifications_failed",
                request_id=str(request.id),
                tenant_id=str(request.tenant_id),
                approved=approved,
            )

    async def _get_tenant_slug(self, tenant_id: UUID) -> str:
        """Resolve tenant slug for human-facing notifications."""
        result = await self._db.execute(select(Tenant.slug).where(Tenant.id == tenant_id))
        slug = result.scalar_one_or_none()
        if isinstance(slug, str) and slug.strip():
            return slug
        return "unknown"

    async def _get_user_email(self, subject: str) -> str | None:
        """Resolve user email by subject from the users table."""
        result = await self._db.execute(
            select(User.email).where(User.subject == subject, User.email.is_not(None))
        )
        email = result.scalar_one_or_none()
        if isinstance(email, str) and email.strip():
            return email.strip()
        return None

    async def _resolve_tenant_admin_emails(self, tenant_id: UUID) -> list[str]:
        """Resolve tenant admin email recipients for tenant-scoped notifications."""
        result = await self._db.execute(
            select(User.email)
            .join(TenantMember, User.subject == TenantMember.user_subject)
            .where(
                TenantMember.tenant_id == tenant_id,
                TenantMember.role == TenantRole.TENANT_ADMIN,
                User.email.is_not(None),
            )
        )
        emails = [
            email.strip() for email in result.scalars().all() if isinstance(email, str) and email
        ]
        return self._dedupe_emails(emails)

    def _resolve_admin_fallback_emails(self) -> list[str]:
        settings = get_settings()
        return self._dedupe_emails(settings.notifications_admin_fallback_emails_all)

    async def _notify_request_created(
        self,
        *,
        request: RoleUpgradeRequest,
        tenant_slug: str,
        requester_email: str | None,
    ) -> None:
        email_client = EmailClient()
        requester_template = build_role_request_submitted_requester_email(
            tenant_slug=tenant_slug,
            requested_role=request.requested_role.value,
            reason=request.reason,
        )
        admin_template = build_role_request_submitted_admin_email(
            tenant_slug=tenant_slug,
            requested_role=request.requested_role.value,
            requester_subject=request.user_subject,
            reason=request.reason,
        )

        requester_recipient = (requester_email or "").strip() or await self._get_user_email(
            request.user_subject
        )
        if requester_recipient:
            await email_client.send_email(
                [requester_recipient],
                subject=requester_template.subject,
                text_body=requester_template.text_body,
                html_body=requester_template.html_body,
            )
        else:
            logger.warning(
                "role_request_requester_email_missing",
                request_id=str(request.id),
                user_subject=request.user_subject,
            )

        admin_recipients = await self._resolve_tenant_admin_emails(request.tenant_id)
        if not admin_recipients:
            admin_recipients = self._resolve_admin_fallback_emails()

        if admin_recipients:
            await email_client.send_email(
                admin_recipients,
                subject=admin_template.subject,
                text_body=admin_template.text_body,
                html_body=admin_template.html_body,
            )
        else:
            logger.warning(
                "role_request_admin_recipients_missing",
                request_id=str(request.id),
                tenant_id=str(request.tenant_id),
            )

    async def _notify_request_reviewed(
        self,
        *,
        request: RoleUpgradeRequest,
        tenant_slug: str,
        approved: bool,
    ) -> None:
        requester_email = await self._get_user_email(request.user_subject)
        if not requester_email:
            logger.warning(
                "role_request_decision_email_missing",
                request_id=str(request.id),
                user_subject=request.user_subject,
            )
            return

        template = build_role_request_decision_email(
            tenant_slug=tenant_slug,
            requested_role=request.requested_role.value,
            approved=approved,
            review_note=request.review_note,
        )
        email_client = EmailClient()
        await email_client.send_email(
            [requester_email],
            subject=template.subject,
            text_body=template.text_body,
            html_body=template.html_body,
        )

    @staticmethod
    def _dedupe_emails(emails: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for email in emails:
            normalized = email.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(normalized)
        return result
