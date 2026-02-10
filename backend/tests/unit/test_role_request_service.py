"""Unit tests for the RoleRequestService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.security.oidc import TokenPayload
from app.db.models import RoleRequestStatus, RoleUpgradeRequest, TenantMember, TenantRole
from app.modules.onboarding.role_request_service import RoleRequestService


def _make_user(
    sub: str = "user-1",
    roles: list[str] | None = None,
) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email="user@example.com",
        email_verified=True,
        preferred_username="testuser",
        roles=roles or ["viewer"],
        bpn=None,
        org=None,
        clearance=None,
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_request_publisher(mock_db: AsyncMock) -> None:
    """Creating a publisher role request succeeds."""
    tenant_id = uuid4()
    user = _make_user()

    # No existing pending request
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[existing_result])
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    with patch(
        "app.modules.onboarding.role_request_service.emit_audit_event",
        new_callable=AsyncMock,
    ):
        svc = RoleRequestService(mock_db)
        result = await svc.create_request(
            tenant_id=tenant_id,
            user=user,
            requested_role="publisher",
            reason="I need to create DPPs",
        )

    assert isinstance(result, RoleUpgradeRequest)
    assert result.requested_role == TenantRole.PUBLISHER
    assert result.status == RoleRequestStatus.PENDING


@pytest.mark.asyncio
async def test_create_request_viewer_rejected(mock_db: AsyncMock) -> None:
    """Requesting viewer role (the default) raises ValueError."""
    svc = RoleRequestService(mock_db)
    user = _make_user()
    with pytest.raises(ValueError, match="Cannot request viewer"):
        await svc.create_request(
            tenant_id=uuid4(),
            user=user,
            requested_role="viewer",
        )


@pytest.mark.asyncio
async def test_create_request_tenant_admin_rejected(mock_db: AsyncMock) -> None:
    """Self-requesting tenant_admin is forbidden."""
    svc = RoleRequestService(mock_db)
    user = _make_user()
    with pytest.raises(ValueError, match="Cannot self-request tenant_admin"):
        await svc.create_request(
            tenant_id=uuid4(),
            user=user,
            requested_role="tenant_admin",
        )


@pytest.mark.asyncio
async def test_create_request_duplicate_pending_rejected(mock_db: AsyncMock) -> None:
    """Cannot create a second pending request."""
    tenant_id = uuid4()
    user = _make_user()

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = MagicMock(spec=RoleUpgradeRequest)
    mock_db.execute = AsyncMock(side_effect=[existing_result])

    svc = RoleRequestService(mock_db)
    with pytest.raises(ValueError, match="pending role request already exists"):
        await svc.create_request(
            tenant_id=tenant_id,
            user=user,
            requested_role="publisher",
        )


@pytest.mark.asyncio
async def test_review_approve_updates_membership(mock_db: AsyncMock) -> None:
    """Approving a request updates the TenantMember role."""
    tenant_id = uuid4()
    request_id = uuid4()
    reviewer = _make_user(sub="admin-1", roles=["admin"])

    # The pending request
    req = RoleUpgradeRequest(
        tenant_id=tenant_id,
        user_subject="user-1",
        requested_role=TenantRole.PUBLISHER,
        status=RoleRequestStatus.PENDING,
    )
    req.id = request_id

    request_result = MagicMock()
    request_result.scalar_one_or_none.return_value = req

    # Existing membership
    member = MagicMock(spec=TenantMember)
    member.role = TenantRole.VIEWER
    member_result = MagicMock()
    member_result.scalar_one_or_none.return_value = member

    mock_db.execute = AsyncMock(side_effect=[request_result, member_result])
    mock_db.flush = AsyncMock()

    with (
        patch(
            "app.modules.onboarding.role_request_service.emit_audit_event",
            new_callable=AsyncMock,
        ),
        patch(
            "app.modules.onboarding.role_request_service.KeycloakAdminClient",
        ) as kc_mock,
    ):
        kc_instance = MagicMock()
        kc_instance.assign_realm_role = AsyncMock(return_value=True)
        kc_mock.return_value = kc_instance

        svc = RoleRequestService(mock_db)
        result = await svc.review_request(
            request_id=request_id,
            tenant_id=tenant_id,
            approved=True,
            reviewer=reviewer,
        )

    assert result.status == RoleRequestStatus.APPROVED
    assert member.role == TenantRole.PUBLISHER


@pytest.mark.asyncio
async def test_review_deny_keeps_membership(mock_db: AsyncMock) -> None:
    """Denying a request does not change membership."""
    tenant_id = uuid4()
    request_id = uuid4()
    reviewer = _make_user(sub="admin-1", roles=["admin"])

    req = RoleUpgradeRequest(
        tenant_id=tenant_id,
        user_subject="user-1",
        requested_role=TenantRole.PUBLISHER,
        status=RoleRequestStatus.PENDING,
    )
    req.id = request_id

    request_result = MagicMock()
    request_result.scalar_one_or_none.return_value = req

    mock_db.execute = AsyncMock(side_effect=[request_result])
    mock_db.flush = AsyncMock()

    with patch(
        "app.modules.onboarding.role_request_service.emit_audit_event",
        new_callable=AsyncMock,
    ):
        svc = RoleRequestService(mock_db)
        result = await svc.review_request(
            request_id=request_id,
            tenant_id=tenant_id,
            approved=False,
            reviewer=reviewer,
            review_note="Not enough justification",
        )

    assert result.status == RoleRequestStatus.DENIED
    assert result.review_note == "Not enough justification"


@pytest.mark.asyncio
async def test_review_already_reviewed_rejected(mock_db: AsyncMock) -> None:
    """Cannot review an already-reviewed request."""
    tenant_id = uuid4()
    request_id = uuid4()
    reviewer = _make_user(sub="admin-1", roles=["admin"])

    req = RoleUpgradeRequest(
        tenant_id=tenant_id,
        user_subject="user-1",
        requested_role=TenantRole.PUBLISHER,
        status=RoleRequestStatus.APPROVED,
    )
    req.id = request_id

    request_result = MagicMock()
    request_result.scalar_one_or_none.return_value = req

    mock_db.execute = AsyncMock(side_effect=[request_result])

    svc = RoleRequestService(mock_db)
    with pytest.raises(ValueError, match="already approved"):
        await svc.review_request(
            request_id=request_id,
            tenant_id=tenant_id,
            approved=True,
            reviewer=reviewer,
        )
