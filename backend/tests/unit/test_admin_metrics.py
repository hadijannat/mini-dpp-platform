"""Unit tests for admin metrics and tenant member role updates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.models import TenantRole
from app.modules.tenants.service import TenantService


class TestUpdateMemberRole:
    """Tests for TenantService.update_member_role."""

    @pytest.fixture()
    def session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def service(self, session: AsyncMock) -> TenantService:
        return TenantService(session)

    @pytest.mark.asyncio()
    async def test_update_existing_member(self, service: TenantService) -> None:
        member = MagicMock()
        member.role = TenantRole.VIEWER
        service.get_member = AsyncMock(return_value=member)  # type: ignore[method-assign]

        result = await service.update_member_role(uuid4(), "user-sub", TenantRole.PUBLISHER)

        assert result is member
        assert member.role == TenantRole.PUBLISHER

    @pytest.mark.asyncio()
    async def test_update_nonexistent_member(self, service: TenantService) -> None:
        service.get_member = AsyncMock(return_value=None)  # type: ignore[method-assign]

        result = await service.update_member_role(uuid4(), "missing-user", TenantRole.PUBLISHER)

        assert result is None

    @pytest.mark.asyncio()
    async def test_update_to_tenant_admin(self, service: TenantService) -> None:
        member = MagicMock()
        member.role = TenantRole.VIEWER
        service.get_member = AsyncMock(return_value=member)  # type: ignore[method-assign]

        result = await service.update_member_role(uuid4(), "user-sub", TenantRole.TENANT_ADMIN)

        assert result is member
        assert member.role == TenantRole.TENANT_ADMIN


class TestPlatformMetrics:
    """Tests for TenantService.get_platform_metrics."""

    @pytest.fixture()
    def session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def service(self, session: AsyncMock) -> TenantService:
        return TenantService(session)

    @pytest.mark.asyncio()
    async def test_metrics_returns_list(self, service: TenantService) -> None:
        """Test that get_platform_metrics returns a list of dicts."""
        mock_row = MagicMock()
        mock_row.tenant_id = uuid4()
        mock_row.slug = "test-tenant"
        mock_row.name = "Test Tenant"
        mock_row.status = MagicMock(value="active")
        mock_row.total_dpps = 5
        mock_row.draft_dpps = 2
        mock_row.published_dpps = 2
        mock_row.archived_dpps = 1
        mock_row.total_revisions = 10
        mock_row.total_members = 3
        mock_row.total_epcis_events = 7
        mock_row.total_audit_events = 20

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        service._session.execute = AsyncMock(return_value=mock_result)

        rows = await service.get_platform_metrics()

        assert len(rows) == 1
        assert rows[0]["slug"] == "test-tenant"
        assert rows[0]["total_dpps"] == 5
        assert rows[0]["published_dpps"] == 2
        assert rows[0]["total_members"] == 3

    @pytest.mark.asyncio()
    async def test_metrics_empty_tenants(self, service: TenantService) -> None:
        """Test that get_platform_metrics handles no tenants."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        service._session.execute = AsyncMock(return_value=mock_result)

        rows = await service.get_platform_metrics()

        assert rows == []

    @pytest.mark.asyncio()
    async def test_metrics_status_string_fallback(self, service: TenantService) -> None:
        """Test that status works when it's a plain string (not enum)."""
        mock_row = MagicMock()
        mock_row.tenant_id = uuid4()
        mock_row.slug = "plain"
        mock_row.name = "Plain"
        mock_row.status = "active"  # plain string, not enum
        mock_row.total_dpps = 0
        mock_row.draft_dpps = 0
        mock_row.published_dpps = 0
        mock_row.archived_dpps = 0
        mock_row.total_revisions = 0
        mock_row.total_members = 0
        mock_row.total_epcis_events = 0
        mock_row.total_audit_events = 0

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        service._session.execute = AsyncMock(return_value=mock_result)

        rows = await service.get_platform_metrics()

        assert rows[0]["status"] == "active"


class TestMetricsResponseSchema:
    """Tests for the PlatformMetricsResponse schema."""

    def test_totals_computation(self) -> None:
        from app.modules.tenants.router import PlatformMetricsResponse, TenantMetrics

        t1 = TenantMetrics(
            tenant_id="id1",
            slug="a",
            name="A",
            status="active",
            total_dpps=3,
            draft_dpps=1,
            published_dpps=2,
            archived_dpps=0,
            total_revisions=5,
            total_members=2,
            total_epcis_events=4,
            total_audit_events=10,
        )
        t2 = TenantMetrics(
            tenant_id="id2",
            slug="b",
            name="B",
            status="active",
            total_dpps=7,
            draft_dpps=3,
            published_dpps=3,
            archived_dpps=1,
            total_revisions=15,
            total_members=5,
            total_epcis_events=12,
            total_audit_events=30,
        )

        resp = PlatformMetricsResponse(
            tenants=[t1, t2],
            totals={
                "total_tenants": 2,
                "total_dpps": 10,
                "total_published": 5,
                "total_members": 7,
                "total_epcis_events": 16,
                "total_audit_events": 40,
            },
        )

        assert resp.totals["total_tenants"] == 2
        assert resp.totals["total_dpps"] == 10
        assert len(resp.tenants) == 2
