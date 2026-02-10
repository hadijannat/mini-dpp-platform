"""
Auto-provisioning service for new user onboarding.

Creates tenant memberships and user records on first login.
"""

from dataclasses import dataclass
from typing import cast

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
from app.modules.onboarding.schemas import OnboardingBlocker, OnboardingNextAction

logger = get_logger(__name__)


@dataclass(slots=True)
class OnboardingEvaluation:
    """Derived onboarding context used by status + provisioning flows."""

    tenant_slug: str | None
    tenant: Tenant | None
    blockers: list[OnboardingBlocker]


class OnboardingProvisioningError(ValueError):
    """Raised when explicit onboarding provisioning cannot proceed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OnboardingService:
    """Handles auto-provisioning of new users into the default tenant."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def try_auto_provision(self, user: TokenPayload) -> TenantMember | None:
        """
        Auto-provision a user into the default tenant as VIEWER.

        Returns the new TenantMember if created, None if:
        - Onboarding is disabled
        - Email verification is required but missing
        - Target tenant doesn't exist or is inactive
        - User is already a member (idempotent)
        """
        evaluation = await self._evaluate_onboarding(user)
        if evaluation.blockers:
            if "email_unverified" in evaluation.blockers:
                logger.info(
                    "onboarding_email_not_verified",
                    sub=user.sub,
                )
            return None

        if not evaluation.tenant or not evaluation.tenant_slug:
            logger.info(
                "onboarding_target_tenant_unavailable",
                sub=user.sub,
                tenant_slug=evaluation.tenant_slug,
            )
            return None

        # Check existing membership (idempotent)
        existing = await self._db.execute(
            select(TenantMember).where(
                TenantMember.tenant_id == evaluation.tenant.id,
                TenantMember.user_subject == user.sub,
            )
        )
        if existing.scalar_one_or_none():
            return None

        # Create membership
        membership = TenantMember(
            tenant_id=evaluation.tenant.id,
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
            tenant_id=evaluation.tenant.id,
            metadata={"tenant_slug": evaluation.tenant_slug, "role": TenantRole.VIEWER.value},
        )

        logger.info(
            "user_auto_provisioned",
            sub=user.sub,
            tenant=evaluation.tenant_slug,
            role=TenantRole.VIEWER.value,
        )
        return membership

    async def get_onboarding_status(self, user: TokenPayload) -> dict[str, object]:
        """Check whether the user has been provisioned into a tenant."""
        evaluation = await self._evaluate_onboarding(user)
        role: str | None = None
        provisioned = False

        if evaluation.tenant and evaluation.tenant.status == TenantStatus.ACTIVE:
            membership_result = await self._db.execute(
                select(TenantMember).where(
                    TenantMember.tenant_id == evaluation.tenant.id,
                    TenantMember.user_subject == user.sub,
                )
            )
            membership = membership_result.scalar_one_or_none()
            if membership:
                provisioned = True
                role = membership.role.value

        next_actions = self._compute_next_actions(
            provisioned=provisioned,
            role=role,
            blockers=evaluation.blockers,
        )
        return {
            "provisioned": provisioned,
            "tenant_slug": evaluation.tenant_slug,
            "role": role,
            "email_verified": user.email_verified,
            "blockers": evaluation.blockers,
            "next_actions": next_actions,
        }

    async def provision_user(self, user: TokenPayload) -> dict[str, object]:
        """Run explicit provisioning and fail fast with machine-readable errors."""
        status = await self.get_onboarding_status(user)
        if cast(bool, status["provisioned"]):
            return status

        blockers = cast(list[OnboardingBlocker], status["blockers"])
        if blockers:
            code, message = self._to_provisioning_error(blockers)
            raise OnboardingProvisioningError(code=code, message=message)

        membership = await self.try_auto_provision(user)
        if not membership:
            raise OnboardingProvisioningError(
                code="onboarding_provisioning_failed",
                message="Provisioning could not be completed. Please try again.",
            )

        role = membership.role.value
        return {
            "provisioned": True,
            "tenant_slug": status["tenant_slug"],
            "role": role,
            "email_verified": status["email_verified"],
            "blockers": [],
            "next_actions": self._compute_next_actions(provisioned=True, role=role, blockers=[]),
        }

    async def _evaluate_onboarding(self, user: TokenPayload) -> OnboardingEvaluation:
        """Resolve target tenant and all deterministic onboarding blockers."""
        settings = get_settings()
        slug = settings.onboarding_auto_join_tenant_slug
        blockers: list[OnboardingBlocker] = []
        tenant: Tenant | None = None

        if not slug:
            blockers.append("onboarding_disabled")
            return OnboardingEvaluation(tenant_slug=None, tenant=None, blockers=blockers)

        if settings.onboarding_require_email_verified and not user.email_verified:
            blockers.append("email_unverified")

        result = await self._db.execute(select(Tenant).where(Tenant.slug == slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            blockers.append("tenant_missing")
            return OnboardingEvaluation(tenant_slug=slug, tenant=None, blockers=blockers)

        if tenant.status != TenantStatus.ACTIVE:
            blockers.append("tenant_inactive")

        return OnboardingEvaluation(tenant_slug=slug, tenant=tenant, blockers=blockers)

    def _compute_next_actions(
        self,
        *,
        provisioned: bool,
        role: str | None,
        blockers: list[OnboardingBlocker],
    ) -> list[OnboardingNextAction]:
        actions: list[OnboardingNextAction] = []

        if not provisioned and not blockers:
            actions.append("provision")
        if "email_unverified" in blockers:
            actions.append("resend_verification")
        if provisioned and role == "viewer":
            actions.append("request_role_upgrade")
        actions.append("go_home")
        return actions

    def _to_provisioning_error(self, blockers: list[OnboardingBlocker]) -> tuple[str, str]:
        if "email_unverified" in blockers:
            return (
                "onboarding_email_not_verified",
                "Email verification is required before onboarding.",
            )
        if "onboarding_disabled" in blockers:
            return ("onboarding_disabled", "Onboarding is currently disabled.")
        if "tenant_missing" in blockers:
            return (
                "onboarding_tenant_not_found",
                "Onboarding target tenant was not found.",
            )
        if "tenant_inactive" in blockers:
            return (
                "onboarding_tenant_inactive",
                "Onboarding target tenant is inactive.",
            )
        return ("onboarding_blocked", "Onboarding is currently blocked.")

    async def _ensure_user_record(self, user: TokenPayload) -> None:
        """Create or update the User row from JWT claims."""
        result = await self._db.execute(select(User).where(User.subject == user.sub))
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
