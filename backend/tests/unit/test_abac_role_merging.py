"""
Unit tests for ABAC role merging behavior.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.security.abac import build_subject_context
from app.core.security.oidc import TokenPayload


def _mock_user(roles: list[str]) -> TokenPayload:
    """Create a mock user with specified roles."""
    return TokenPayload(
        sub="test-user-123",
        email="test@example.com",
        preferred_username="test",
        roles=roles,
        bpn="BPNL00000001TEST",
        org="Test Org",
        clearance="public",
        exp=datetime.now(UTC),
        iat=datetime.now(UTC),
        raw_claims={},
    )


@dataclass
class MockTenantContext:
    """Mock tenant context for testing."""

    tenant_id: str
    tenant_slug: str
    roles: list[str]
    is_publisher: bool
    is_tenant_admin: bool
    user: TokenPayload


class TestBuildSubjectContext:
    """Tests for build_subject_context role merging."""

    def test_no_tenant_uses_jwt_roles(self):
        """Without tenant context, JWT roles should be used directly."""
        user = _mock_user(["publisher", "auditor"])
        context = build_subject_context(user, tenant=None)

        assert set(context["roles"]) == {"publisher", "auditor"}

    def test_tenant_context_replaces_non_platform_roles(self):
        """Tenant context should replace non-platform JWT roles."""
        user = _mock_user(["publisher", "some-custom-role"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["viewer"],
            is_publisher=False,
            is_tenant_admin=False,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        # Only tenant role (viewer) should be present, not publisher
        assert "viewer" in context["roles"]
        assert "publisher" not in context["roles"]
        assert "some-custom-role" not in context["roles"]

    def test_tenant_context_preserves_admin_role(self):
        """Platform 'admin' role should be preserved with tenant context."""
        user = _mock_user(["admin", "publisher"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["viewer"],
            is_publisher=False,
            is_tenant_admin=False,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        # Admin should be preserved, publisher should not
        assert "admin" in context["roles"]
        assert "viewer" in context["roles"]
        assert "publisher" not in context["roles"]

    def test_tenant_context_preserves_auditor_role(self):
        """Platform 'auditor' role should be preserved with tenant context."""
        user = _mock_user(["auditor", "publisher"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["viewer"],
            is_publisher=False,
            is_tenant_admin=False,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        # Auditor should be preserved
        assert "auditor" in context["roles"]
        assert "viewer" in context["roles"]
        assert "publisher" not in context["roles"]

    def test_tenant_context_merges_admin_and_auditor(self):
        """Both admin and auditor should be preserved alongside tenant roles."""
        user = _mock_user(["admin", "auditor", "some-other-role"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["publisher", "tenant_admin"],
            is_publisher=True,
            is_tenant_admin=True,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        expected_roles = {"admin", "auditor", "publisher", "tenant_admin"}
        assert set(context["roles"]) == expected_roles

    def test_no_duplicate_roles_after_merge(self):
        """Merged roles should not have duplicates."""
        user = _mock_user(["admin", "publisher"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["admin", "publisher"],  # Duplicate admin
            is_publisher=True,
            is_tenant_admin=False,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        # Should have no duplicates
        assert len(context["roles"]) == len(set(context["roles"]))
        assert "admin" in context["roles"]
        assert "publisher" in context["roles"]

    def test_subject_context_includes_other_fields(self):
        """Subject context should include all expected fields."""
        user = _mock_user(["publisher"])
        tenant = MockTenantContext(
            tenant_id=str(uuid4()),
            tenant_slug="test-tenant",
            roles=["viewer"],
            is_publisher=False,
            is_tenant_admin=False,
            user=user,
        )

        context = build_subject_context(user, tenant=tenant)

        assert context["sub"] == "test-user-123"
        assert context["email"] == "test@example.com"
        assert context["bpn"] == "BPNL00000001TEST"
        assert context["clearance"] == "public"
        assert context["is_publisher"] is False
        assert context["tenant_slug"] == "test-tenant"
