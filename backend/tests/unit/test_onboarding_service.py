"""Unit tests for the OnboardingService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security.oidc import TokenPayload
from app.db.models import Tenant, TenantMember, TenantRole, TenantStatus
from app.modules.onboarding.service import OnboardingService


def _make_user(
    sub: str = "user-1",
    email: str = "user@example.com",
    email_verified: bool = True,
) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email=email,
        email_verified=email_verified,
        preferred_username="testuser",
        roles=["viewer"],
        bpn=None,
        org=None,
        clearance=None,
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


def _make_tenant(slug: str = "default") -> Tenant:
    tenant = MagicMock(spec=Tenant)
    tenant.id = uuid4()
    tenant.slug = slug
    tenant.status = TenantStatus.ACTIVE
    return tenant


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_auto_provision_creates_membership(mock_db: AsyncMock) -> None:
    """Happy path: new user is provisioned as VIEWER."""
    tenant = _make_tenant()
    user = _make_user()

    # First execute: select Tenant → returns tenant
    # Second execute: select TenantMember → returns None (no existing membership)
    # Third execute: select User → returns None (no existing user)
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result, user_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    with patch("app.modules.onboarding.service.emit_audit_event", new_callable=AsyncMock):
        svc = OnboardingService(mock_db)
        result = await svc.try_auto_provision(user)

    assert result is not None
    # Verify a TenantMember was added
    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    member = next((obj for obj in added_objects if isinstance(obj, TenantMember)), None)
    assert member is not None
    assert member.role == TenantRole.VIEWER


@pytest.mark.asyncio
async def test_auto_provision_returns_none_when_disabled(mock_db: AsyncMock) -> None:
    """Returns None when onboarding_auto_join_tenant_slug is None."""
    user = _make_user()

    with patch("app.modules.onboarding.service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.onboarding_auto_join_tenant_slug = None
        mock_settings.return_value = settings

        svc = OnboardingService(mock_db)
        result = await svc.try_auto_provision(user)

    assert result is None


@pytest.mark.asyncio
async def test_auto_provision_blocks_unverified_email(mock_db: AsyncMock) -> None:
    """Returns None when email is not verified but required."""
    user = _make_user(email_verified=False)

    with patch("app.modules.onboarding.service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.onboarding_auto_join_tenant_slug = "default"
        settings.onboarding_require_email_verified = True
        mock_settings.return_value = settings

        svc = OnboardingService(mock_db)
        result = await svc.try_auto_provision(user)

    assert result is None


@pytest.mark.asyncio
async def test_auto_provision_idempotent(mock_db: AsyncMock) -> None:
    """Returns None when user already has a membership (idempotent)."""
    tenant = _make_tenant()
    user = _make_user()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant

    existing_member = MagicMock(spec=TenantMember)
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = existing_member

    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result])

    svc = OnboardingService(mock_db)
    result = await svc.try_auto_provision(user)

    assert result is None


@pytest.mark.asyncio
async def test_get_onboarding_status_provisioned(mock_db: AsyncMock) -> None:
    """Returns provisioned=True when membership exists."""
    tenant = _make_tenant()
    user = _make_user()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant

    member = MagicMock(spec=TenantMember)
    member.role = TenantRole.VIEWER
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = member

    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result])

    svc = OnboardingService(mock_db)
    result = await svc.get_onboarding_status(user)

    assert result["provisioned"] is True
    assert result["role"] == "viewer"


@pytest.mark.asyncio
async def test_get_onboarding_status_not_provisioned(mock_db: AsyncMock) -> None:
    """Returns provisioned=False when no membership exists."""
    tenant = _make_tenant()
    user = _make_user()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result])

    svc = OnboardingService(mock_db)
    result = await svc.get_onboarding_status(user)

    assert result["provisioned"] is False
    assert result["tenant_slug"] == "default"
