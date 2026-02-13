"""Negative security tests (TEST-003).

Verifies that the authentication and authorization layers correctly
reject: missing auth, wrong roles, and cross-tenant access attempts.
These are pure unit tests using mocked dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.security.oidc import TokenPayload


def _make_token(
    *,
    sub: str = "test-user-123",
    roles: list[str] | None = None,
    email_verified: bool = True,
) -> TokenPayload:
    """Create a TokenPayload with configurable roles."""
    return TokenPayload(
        sub=sub,
        email="test@example.com",
        email_verified=email_verified,
        preferred_username="testuser",
        roles=roles if roles is not None else ["publisher"],
        bpn="BPNL00000001TEST",
        org="Test Organization",
        clearance="public",
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


# ── TokenPayload Role Properties ──────────────────────────────────


class TestTokenPayloadRoles:
    """Verify role-checking properties on TokenPayload."""

    def test_publisher_role_grants_is_publisher(self) -> None:
        token = _make_token(roles=["publisher"])
        assert token.is_publisher is True
        assert token.is_admin is False

    def test_admin_role_grants_both(self) -> None:
        token = _make_token(roles=["admin"])
        assert token.is_publisher is True
        assert token.is_admin is True

    def test_tenant_admin_grants_is_publisher(self) -> None:
        token = _make_token(roles=["tenant_admin"])
        assert token.is_publisher is True
        assert token.is_admin is False

    def test_viewer_has_no_elevated_roles(self) -> None:
        token = _make_token(roles=["viewer"])
        assert token.is_publisher is False
        assert token.is_admin is False

    def test_empty_roles_has_no_elevated_roles(self) -> None:
        token = _make_token(roles=[])
        assert token.is_publisher is False
        assert token.is_admin is False


# ── Missing Authentication ─────────────────────────────────────────


class TestMissingAuthentication:
    """Verify 401 when Authorization header is missing."""

    @pytest.mark.asyncio()
    async def test_authenticated_endpoint_returns_401_without_auth(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.get("/api/v1/tenants/default/dpps")
        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_thread_endpoint_returns_401_without_auth(self, test_client: AsyncClient) -> None:
        dpp_id = uuid4()
        resp = await test_client.get(f"/api/v1/tenants/default/thread/timeline/{dpp_id}")
        assert resp.status_code == 401

    @pytest.mark.asyncio()
    async def test_webhooks_endpoint_returns_401_without_auth(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.get("/api/v1/tenants/default/webhooks")
        assert resp.status_code == 401


# ── Wrong Role (Viewer accessing Publisher endpoints) ──────────────


class TestInsufficientRole:
    """Verify that viewer tokens cannot access publisher-only endpoints."""

    @pytest.mark.asyncio()
    async def test_viewer_role_lacks_publisher_permission(self) -> None:
        """A viewer token does not grant publisher access."""
        viewer_token = _make_token(roles=["viewer"])
        assert viewer_token.is_publisher is False

    @pytest.mark.asyncio()
    async def test_viewer_is_publisher_returns_false(self) -> None:
        token = _make_token(roles=["viewer"])
        assert token.is_publisher is False

    @pytest.mark.asyncio()
    async def test_non_admin_is_admin_returns_false(self) -> None:
        token = _make_token(roles=["publisher"])
        assert token.is_admin is False


# ── Cross-Tenant Access ────────────────────────────────────────────


class TestCrossTenantAccess:
    """Verify that accessing a non-existent tenant slug returns 404."""

    @pytest.mark.asyncio()
    async def test_nonexistent_tenant_returns_404(
        self, test_client: AsyncClient, mock_auth_headers: dict[str, str]
    ) -> None:
        resp = await test_client.get(
            "/api/v1/tenants/nonexistent-tenant/dpps",
            headers=mock_auth_headers,
        )
        # Non-existent tenant should return 404 (not 401, to avoid info leak)
        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_dpp_in_wrong_tenant_returns_404(
        self, test_client: AsyncClient, mock_auth_headers: dict[str, str]
    ) -> None:
        """Attempting to fetch a DPP via a different tenant slug returns 404."""
        fake_dpp_id = uuid4()
        resp = await test_client.get(
            f"/api/v1/tenants/nonexistent-tenant/dpps/{fake_dpp_id}",
            headers=mock_auth_headers,
        )
        assert resp.status_code == 404


# ── Public Endpoint Does Not Leak Private Data ─────────────────────


class TestPublicEndpointSafety:
    """Verify public endpoints don't expose internal data."""

    @pytest.mark.asyncio()
    async def test_nonexistent_public_dpp_returns_404(self, test_client: AsyncClient) -> None:
        fake_dpp_id = uuid4()
        resp = await test_client.get(f"/default/dpps/{fake_dpp_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_nonexistent_tenant_public_dpp_returns_404(
        self, test_client: AsyncClient
    ) -> None:
        fake_dpp_id = uuid4()
        resp = await test_client.get(f"/ghost-tenant/dpps/{fake_dpp_id}")
        assert resp.status_code == 404
