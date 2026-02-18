"""Unit tests for role request router response enrichment."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.security.oidc import TokenPayload
from app.db.models import RoleRequestStatus, RoleUpgradeRequest, TenantRole
from app.modules.onboarding.role_request_router import list_all_requests, list_my_requests


def _make_user(
    sub: str = "user-1",
    roles: list[str] | None = None,
) -> TokenPayload:
    return TokenPayload(
        sub=sub,
        email="user@example.com",
        email_verified=True,
        preferred_username="test-user",
        roles=roles or ["tenant_admin"],
        bpn=None,
        org=None,
        clearance=None,
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


def _make_request(user_subject: str = "user-1") -> RoleUpgradeRequest:
    request = RoleUpgradeRequest(
        tenant_id=uuid4(),
        user_subject=user_subject,
        requested_role=TenantRole.PUBLISHER,
        status=RoleRequestStatus.PENDING,
        reason="Need publisher access",
    )
    request.id = uuid4()
    request.created_at = datetime.now(UTC)
    return request


@pytest.mark.asyncio
async def test_list_all_requests_includes_requester_identity() -> None:
    """Admin listing returns requester email/display name when available."""
    req = _make_request()
    context = SimpleNamespace(tenant_id=req.tenant_id, user=_make_user(sub="admin-1", roles=["admin"]))
    db = AsyncMock()

    with (
        patch(
            "app.modules.onboarding.role_request_router.RoleRequestService.list_requests",
            new=AsyncMock(return_value=[req]),
        ),
        patch(
            "app.modules.onboarding.role_request_router.RoleRequestService.get_requester_identity_map",
            new=AsyncMock(return_value={"user-1": ("requester@example.com", "Requester User")}),
        ),
    ):
        response = await list_all_requests(db=db, context=context, status_filter=None)

    assert len(response) == 1
    assert response[0].requester_email == "requester@example.com"
    assert response[0].requester_display_name == "Requester User"


@pytest.mark.asyncio
async def test_list_my_requests_handles_missing_requester_identity() -> None:
    """User listing keeps requester fields nullable when user profile is unavailable."""
    req = _make_request()
    context = SimpleNamespace(tenant_id=req.tenant_id, user=_make_user(sub="user-1", roles=["viewer"]))
    db = AsyncMock()

    with (
        patch(
            "app.modules.onboarding.role_request_router.RoleRequestService.get_user_requests",
            new=AsyncMock(return_value=[req]),
        ),
        patch(
            "app.modules.onboarding.role_request_router.RoleRequestService.get_requester_identity_map",
            new=AsyncMock(return_value={}),
        ),
    ):
        response = await list_my_requests(db=db, context=context)

    assert len(response) == 1
    assert response[0].requester_email is None
    assert response[0].requester_display_name is None
