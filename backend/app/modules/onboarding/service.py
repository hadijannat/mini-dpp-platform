"""
Auto-provisioning service for new user onboarding.

Creates tenant memberships and user records on first login.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import emit_audit_event
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security.oidc import TokenPayload
from app.db.models import (
    Tenant,
    TenantMember,
    TenantRole,
    TenantStatus,
    User,
    UserRole,
)

logger = get_logger(__name__)


class OnboardingService:
    """Handles auto-provisioning of new users into the default tenant."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def try_auto_provision(
        self, user: TokenPayload
    ) -> TenantMember | None:
        """
        Auto-provision a user into the default tenant as VIEWER.

        Returns the new TenantMember if created, None if:
        - Onboarding is disabled
        - Email verification is required but missing
        - Target tenant doesn't exist or is inactive
        - User is already a member (idempotent)
        """
        settings = get_settings()

        slug = settings.onboarding_auto_join_tenant_slug
        if not slug:
            return None

        if settings.onboarding_require_email_verified and not user.email_verified:
            logger.info(
                "onboarding_email_not_verified",
                sub=user.sub,
            )
            return None

        # Look up target tenant
        result = await self._db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return None

        # Check existing membership (idempotent)
        existing = await self._db.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id,
                TenantMember.user_subject == user.sub,
            )
        )
        if existing.scalar_one_or_none():
            return None

        # Create membership
        membership = TenantMember(
            tenant_id=tenant.id,
            user_subject=user.sub,
            role=TenantRole.VIEWER,
        )
        self._db.add(membership)

        # Ensure user record exists
        await self._ensure_user_record(user)

        await self._db.flush()

        await emit_audit_event(
            db_session=self._db,
            action="user_onboarded",
            resource_type="tenant_member",
            resource_id=str(membership.id),
            user=user,
            tenant_id=tenant.id,
            metadata={"tenant_slug": slug, "role": TenantRole.VIEWER.value},
        )

        logger.info(
            "user_auto_provisioned",
            sub=user.sub,
            tenant=slug,
            role=TenantRole.VIEWER.value,
        )
        return membership

    async def get_onboarding_status(
        self, user: TokenPayload
    ) -> dict[str, object]:
        """Check whether the user has been provisioned into a tenant."""
        settings = get_settings()
        slug = settings.onboarding_auto_join_tenant_slug
        if not slug:
            return {"provisioned": False, "tenant_slug": None, "role": None}

        result = await self._db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            return {"provisioned": False, "tenant_slug": None, "role": None}

        membership_result = await self._db.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == tenant.id,
                TenantMember.user_subject == user.sub,
            )
        )
        membership = membership_result.scalar_one_or_none()
        if not membership:
            return {"provisioned": False, "tenant_slug": slug, "role": None}

        return {
            "provisioned": True,
            "tenant_slug": slug,
            "role": membership.role.value,
        }

    async def _ensure_user_record(self, user: TokenPayload) -> None:
        """Create or update the User row from JWT claims."""
        result = await self._db.execute(
            select(User).where(User.subject == user.sub)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            if user.email and existing_user.email != user.email:
                existing_user.email = user.email
            display = user.preferred_username or user.email
            if display and existing_user.display_name != display:
                existing_user.display_name = display
        else:
            new_user = User(
                subject=user.sub,
                email=user.email,
                display_name=user.preferred_username or user.email,
                role=UserRole.VIEWER,
                attrs={},
            )
            self._db.add(new_user)
