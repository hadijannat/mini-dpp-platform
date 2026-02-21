"""Router-level tests for tenant domain authorization flows."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import Tenant, TenantDomain, TenantDomainStatus, TenantStatus


@pytest.mark.asyncio
async def test_publisher_cannot_activate_domain(test_client, db_session, mock_auth_headers) -> None:
    tenant_result = await db_session.execute(select(Tenant).where(Tenant.slug == "default"))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(slug="default", name="Default Tenant", status=TenantStatus.ACTIVE)
        db_session.add(tenant)
        await db_session.flush()

    domain = TenantDomain(
        tenant_id=tenant.id,
        hostname="acme.example.com",
        status=TenantDomainStatus.PENDING,
        is_primary=False,
        created_by_subject="test-user-123",
    )
    db_session.add(domain)
    await db_session.commit()

    response = await test_client.patch(
        f"/api/v1/tenants/default/domains/{domain.id}",
        headers=mock_auth_headers,
        json={"status": "active"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Platform admin role required to activate domains"
