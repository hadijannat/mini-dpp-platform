"""Unit tests for onboarding router endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.security.oidc import TokenPayload
from app.modules.onboarding.router import resend_verification_email


def _make_user(
    sub: str = "user-1",
    email: str = "user@example.com",
    email_verified: bool = False,
) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email=email,
        email_verified=email_verified,
        preferred_username="test-user",
        roles=["viewer"],
        bpn=None,
        org=None,
        clearance=None,
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


@pytest.mark.asyncio
async def test_resend_verification_enqueues_email_with_redirect_and_client() -> None:
    """Resend endpoint passes redirect_uri/client_id and returns cooldown metadata."""
    user = _make_user()
    redis_client = AsyncMock()
    redis_client.ttl = AsyncMock(return_value=-2)
    redis_client.set = AsyncMock(return_value=True)

    settings = MagicMock()
    settings.onboarding_verification_resend_cooldown_seconds = 30
    settings.onboarding_verification_redirect_uri = "https://dpp-platform.dev/welcome"
    settings.onboarding_verification_client_id = "dpp-frontend"
    settings.cors_origins = ["https://dpp-platform.dev"]

    with (
        patch("app.modules.onboarding.router.get_settings", return_value=settings),
        patch("app.modules.onboarding.router.get_redis", AsyncMock(return_value=redis_client)),
        patch("app.modules.onboarding.router.KeycloakAdminClient") as keycloak_client_cls,
    ):
        keycloak_client = MagicMock()
        keycloak_client.send_verify_email = AsyncMock(return_value=True)
        keycloak_client_cls.return_value = keycloak_client

        response = await resend_verification_email(user)

    assert response.queued is True
    assert response.cooldown_seconds == 30
    assert isinstance(response.next_allowed_at, str)
    keycloak_client.send_verify_email.assert_awaited_once_with(
        "user-1",
        redirect_uri="https://dpp-platform.dev/welcome",
        client_id="dpp-frontend",
    )


@pytest.mark.asyncio
async def test_resend_verification_rejects_during_cooldown() -> None:
    """Resend endpoint returns HTTP 429 with retry metadata during cooldown."""
    user = _make_user()
    redis_client = AsyncMock()
    redis_client.ttl = AsyncMock(return_value=12)

    settings = MagicMock()
    settings.onboarding_verification_resend_cooldown_seconds = 30
    settings.onboarding_verification_redirect_uri = None
    settings.onboarding_verification_client_id = "dpp-frontend"
    settings.cors_origins = ["https://dpp-platform.dev"]

    with (
        patch("app.modules.onboarding.router.get_settings", return_value=settings),
        patch("app.modules.onboarding.router.get_redis", AsyncMock(return_value=redis_client)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await resend_verification_email(user)

    exc = exc_info.value
    assert exc.status_code == 429
    assert exc.headers is not None
    assert exc.headers["Retry-After"] == "12"
    assert exc.detail["code"] == "verification_resend_cooldown"
    assert exc.detail["cooldown_seconds"] == 12
    assert isinstance(exc.detail["next_allowed_at"], str)


@pytest.mark.asyncio
async def test_resend_verification_rolls_back_cooldown_when_enqueue_fails() -> None:
    """Resend endpoint removes cooldown key when Keycloak enqueue fails."""
    user = _make_user()
    redis_client = AsyncMock()
    redis_client.ttl = AsyncMock(return_value=-2)
    redis_client.set = AsyncMock(return_value=True)
    redis_client.delete = AsyncMock(return_value=1)
    redis_client.expire = AsyncMock()

    settings = MagicMock()
    settings.onboarding_verification_resend_cooldown_seconds = 30
    settings.onboarding_verification_redirect_uri = "https://dpp-platform.dev/welcome"
    settings.onboarding_verification_client_id = "dpp-frontend"
    settings.cors_origins = ["https://dpp-platform.dev"]

    with (
        patch("app.modules.onboarding.router.get_settings", return_value=settings),
        patch("app.modules.onboarding.router.get_redis", AsyncMock(return_value=redis_client)),
        patch("app.modules.onboarding.router.KeycloakAdminClient") as keycloak_client_cls,
        pytest.raises(HTTPException) as exc_info,
    ):
        keycloak_client = MagicMock()
        keycloak_client.send_verify_email = AsyncMock(return_value=False)
        keycloak_client_cls.return_value = keycloak_client

        await resend_verification_email(user)

    exc = exc_info.value
    assert exc.status_code == 503
    assert exc.detail["code"] == "verification_email_enqueue_failed"
    redis_client.delete.assert_awaited_once_with("onboarding:resend-verification:user-1")
    redis_client.expire.assert_not_awaited()
