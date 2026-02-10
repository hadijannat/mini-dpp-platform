"""
Onboarding API endpoints for first-login provisioning.
"""

from fastapi import APIRouter, HTTPException, status

from app.core.keycloak_admin import KeycloakAdminClient
from app.core.security.oidc import CurrentUser
from app.db.session import DbSession
from app.modules.onboarding.schemas import OnboardingStatusResponse, ResendVerificationResponse
from app.modules.onboarding.service import OnboardingProvisioningError, OnboardingService

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
    try:
        result = await svc.provision_user(user)
    except OnboardingProvisioningError as exc:
        response_status = (
            status.HTTP_403_FORBIDDEN
            if exc.code == "onboarding_email_not_verified"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=response_status,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return OnboardingStatusResponse(**result)


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification_email(
    user: CurrentUser,
) -> ResendVerificationResponse:
    """Trigger a Keycloak verification email for the current user."""
    kc = KeycloakAdminClient()
    queued = await kc.send_verify_email(user.sub)
    if not queued:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "verification_email_enqueue_failed",
                "message": "Could not queue a verification email. Please try again later.",
            },
        )
    return ResendVerificationResponse(queued=True)
