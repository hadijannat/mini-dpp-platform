"""Unit tests for the OnboardingService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security.oidc import TokenPayload
from app.db.models import (
    RoleRequestStatus,
    RoleUpgradeRequest,
    Tenant,
    TenantMember,
    TenantRole,
    TenantStatus,
)
from app.modules.onboarding.service import OnboardingProvisioningError, OnboardingService


def _make_user(
    sub: str = "user-1",
    email: str = "user@example.com",
    email_verified: bool = True,
    roles: list[str] | None = None,
) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email=email,
        email_verified=email_verified,
        preferred_username="testuser",
        roles=roles or ["viewer"],
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
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=tenant_result)

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
async def test_auto_provision_uses_publisher_role_from_identity(mock_db: AsyncMock) -> None:
    """Auto-provision infers publisher membership when identity role is publisher."""
    tenant = _make_tenant()
    user = _make_user(roles=["publisher"])

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
    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    member = next((obj for obj in added_objects if isinstance(obj, TenantMember)), None)
    assert member is not None
    assert member.role == TenantRole.PUBLISHER


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
    assert result["email_verified"] is True
    assert result["blockers"] == []
    assert result["next_actions"] == ["request_role_upgrade", "go_home"]


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
    assert result["email_verified"] is True
    assert result["blockers"] == []
    assert result["next_actions"] == ["provision", "go_home"]


@pytest.mark.asyncio
async def test_get_onboarding_status_unverified_email_blocker(mock_db: AsyncMock) -> None:
    """Unverified email surfaces blocker and resend action."""
    tenant = _make_tenant()
    user = _make_user(email_verified=False)

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result])

    svc = OnboardingService(mock_db)
    result = await svc.get_onboarding_status(user)

    assert result["provisioned"] is False
    assert result["blockers"] == ["email_unverified"]
    assert result["next_actions"] == ["resend_verification", "go_home"]


@pytest.mark.asyncio
async def test_get_onboarding_status_syncs_external_role_and_auto_approves_pending(
    mock_db: AsyncMock,
) -> None:
    """Status call reconciles membership + pending request after external role assignment."""
    tenant = _make_tenant()
    user = _make_user(roles=["publisher"])

    member = MagicMock(spec=TenantMember)
    member.id = uuid4()
    member.tenant_id = tenant.id
    member.user_subject = user.sub
    member.role = TenantRole.VIEWER

    pending_request = RoleUpgradeRequest(
        tenant_id=tenant.id,
        user_subject=user.sub,
        requested_role=TenantRole.PUBLISHER,
        status=RoleRequestStatus.PENDING,
        reason="Need to publish",
    )

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = member
    pending_scalars = MagicMock()
    pending_scalars.all.return_value = [pending_request]
    pending_result = MagicMock()
    pending_result.scalars.return_value = pending_scalars

    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result, pending_result])
    mock_db.flush = AsyncMock()

    svc = OnboardingService(mock_db)
    result = await svc.get_onboarding_status(user)

    assert result["provisioned"] is True
    assert result["role"] == "publisher"
    assert result["next_actions"] == ["go_home"]
    assert member.role == TenantRole.PUBLISHER
    assert pending_request.status == RoleRequestStatus.APPROVED
    assert pending_request.reviewed_by == "system:keycloak-sync"
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_user_raises_on_unverified_email(mock_db: AsyncMock) -> None:
    """Explicit provisioning raises machine-readable unverified email error."""
    tenant = _make_tenant()
    user = _make_user(email_verified=False)

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(side_effect=[tenant_result, membership_result])

    svc = OnboardingService(mock_db)
    with pytest.raises(OnboardingProvisioningError, match="Email verification is required"):
        await svc.provision_user(user)


@pytest.mark.asyncio
async def test_provision_user_raises_when_onboarding_disabled(mock_db: AsyncMock) -> None:
    """Explicit provisioning raises deterministic error when onboarding is disabled."""
    user = _make_user()

    with patch("app.modules.onboarding.service.get_settings") as mock_settings:
        settings = MagicMock()
        settings.onboarding_auto_join_tenant_slug = None
        settings.onboarding_require_email_verified = True
        mock_settings.return_value = settings

        svc = OnboardingService(mock_db)
        with pytest.raises(OnboardingProvisioningError) as exc:
            await svc.provision_user(user)

    assert exc.value.code == "onboarding_disabled"
    assert exc.value.message == "Onboarding is currently disabled."


@pytest.mark.asyncio
async def test_provision_user_raises_when_tenant_missing(mock_db: AsyncMock) -> None:
    """Explicit provisioning raises deterministic error when target tenant is missing."""
    user = _make_user()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=tenant_result)

    svc = OnboardingService(mock_db)
    with pytest.raises(OnboardingProvisioningError) as exc:
        await svc.provision_user(user)

    assert exc.value.code == "onboarding_tenant_not_found"
    assert exc.value.message == "Onboarding target tenant was not found."


@pytest.mark.asyncio
async def test_provision_user_raises_when_tenant_inactive(mock_db: AsyncMock) -> None:
    """Explicit provisioning raises deterministic error when target tenant is inactive."""
    tenant = _make_tenant()
    tenant.status = TenantStatus.DISABLED
    user = _make_user()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    mock_db.execute = AsyncMock(return_value=tenant_result)

    svc = OnboardingService(mock_db)
    with pytest.raises(OnboardingProvisioningError) as exc:
        await svc.provision_user(user)

    assert exc.value.code == "onboarding_tenant_inactive"
    assert exc.value.message == "Onboarding target tenant is inactive."


@pytest.mark.asyncio
async def test_provision_user_returns_provisioned_payload_after_success(mock_db: AsyncMock) -> None:
    """Explicit provisioning returns an enriched provisioned payload on success."""
    tenant = _make_tenant()
    user = _make_user()

    tenant_result_initial = MagicMock()
    tenant_result_initial.scalar_one_or_none.return_value = tenant
    membership_result_initial = MagicMock()
    membership_result_initial.scalar_one_or_none.return_value = None

    tenant_result_provision = MagicMock()
    tenant_result_provision.scalar_one_or_none.return_value = tenant
    membership_result_provision = MagicMock()
    membership_result_provision.scalar_one_or_none.return_value = None

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(
        side_effect=[
            tenant_result_initial,
            membership_result_initial,
            tenant_result_provision,
            membership_result_provision,
            user_result,
        ]
    )
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    with patch("app.modules.onboarding.service.emit_audit_event", new_callable=AsyncMock):
        svc = OnboardingService(mock_db)
        result = await svc.provision_user(user)

    assert result["provisioned"] is True
    assert result["role"] == "viewer"
    assert result["email_verified"] is True
    assert result["blockers"] == []
    assert result["next_actions"] == ["request_role_upgrade", "go_home"]
