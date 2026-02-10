"""
Onboarding API endpoints for first-login provisioning.
"""

from fastapi import APIRouter

from app.core.security.oidc import CurrentUser
from app.db.session import DbSession
from app.modules.onboarding.schemas import OnboardingStatusResponse
from app.modules.onboarding.service import OnboardingService

router = APIRouter()


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    db: DbSession,
    user: CurrentUser,
) -> OnboardingStatusResponse:
    """Check whether the current user has been provisioned into a tenant."""
    svc = OnboardingService(db)
    result = await svc.get_onboarding_status(user)
    return OnboardingStatusResponse(**result)


@router.post("/provision", response_model=OnboardingStatusResponse)
async def provision_user(
    db: DbSession,
    user: CurrentUser,
) -> OnboardingStatusResponse:
    """
    Trigger first-login provisioning (idempotent).

    Creates a VIEWER membership in the default tenant if the user
    hasn't been provisioned yet.
    """
    svc = OnboardingService(db)
    await svc.try_auto_provision(user)
    result = await svc.get_onboarding_status(user)
    return OnboardingStatusResponse(**result)
