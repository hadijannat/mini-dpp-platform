"""
Onboarding API endpoints for first-login provisioning.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.keycloak_admin import KeycloakAdminClient
from app.core.logging import get_logger
from app.core.rate_limit import get_redis
from app.core.security.oidc import CurrentUser
from app.db.session import DbSession
from app.modules.onboarding.schemas import OnboardingStatusResponse, ResendVerificationResponse
from app.modules.onboarding.service import OnboardingProvisioningError, OnboardingService

router = APIRouter()
logger = get_logger(__name__)


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
    settings = get_settings()
    cooldown_seconds = settings.onboarding_verification_resend_cooldown_seconds
    request_time = datetime.now(UTC)
    next_allowed_at = (request_time + timedelta(seconds=cooldown_seconds)).isoformat()
    cache_key = f"onboarding:resend-verification:{user.sub}"

    redis_client = await get_redis()
    cache_key_set = False
    if redis_client is not None:
        try:
            existing_ttl = await redis_client.ttl(cache_key)
            if isinstance(existing_ttl, int) and existing_ttl > 0:
                retry_after = existing_ttl
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "verification_resend_cooldown",
                        "message": (
                            "Verification email was sent recently. "
                            "Please wait before requesting another one."
                        ),
                        "cooldown_seconds": retry_after,
                        "next_allowed_at": (
                            datetime.now(UTC) + timedelta(seconds=retry_after)
                        ).isoformat(),
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            cache_key_set = bool(
                await redis_client.set(cache_key, "1", ex=cooldown_seconds, nx=True)
            )
            if not cache_key_set:
                ttl_value = await redis_client.ttl(cache_key)
                retry_after = (
                    ttl_value if isinstance(ttl_value, int) and ttl_value > 0 else cooldown_seconds
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "verification_resend_cooldown",
                        "message": (
                            "Verification email was sent recently. "
                            "Please wait before requesting another one."
                        ),
                        "cooldown_seconds": retry_after,
                        "next_allowed_at": (
                            datetime.now(UTC) + timedelta(seconds=retry_after)
                        ).isoformat(),
                    },
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception:
            logger.warning("verification_resend_cooldown_check_failed", user_sub=user.sub)

    redirect_uri = settings.onboarding_verification_redirect_uri
    if not redirect_uri and settings.cors_origins:
        redirect_uri = f"{settings.cors_origins[0].rstrip('/')}/welcome"

    kc = KeycloakAdminClient()
    queued = await kc.send_verify_email(
        user.sub,
        redirect_uri=redirect_uri,
        client_id=settings.onboarding_verification_client_id,
    )
    if not queued:
        if redis_client is not None and cache_key_set:
            rollback_succeeded = False
            try:
                await redis_client.delete(cache_key)
                rollback_succeeded = True
            except Exception:
                logger.warning(
                    "verification_resend_cooldown_rollback_failed",
                    user_sub=user.sub,
                )
            if not rollback_succeeded:
                rollback_ttl_seconds = min(5, cooldown_seconds)
                try:
                    await redis_client.expire(cache_key, rollback_ttl_seconds)
                    logger.warning(
                        "verification_resend_cooldown_rollback_degraded",
                        user_sub=user.sub,
                        rollback_ttl_seconds=rollback_ttl_seconds,
                    )
                except Exception:
                    logger.exception(
                        "verification_resend_cooldown_rollback_expire_failed",
                        user_sub=user.sub,
                    )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "verification_email_enqueue_failed",
                "message": "Could not queue a verification email. Please try again later.",
            },
        )
    return ResendVerificationResponse(
        queued=True,
        cooldown_seconds=cooldown_seconds,
        next_allowed_at=next_allowed_at,
    )
