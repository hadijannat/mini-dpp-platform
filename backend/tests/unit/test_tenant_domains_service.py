"""Unit tests for tenant domain normalization and validation."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.tenant_domains.service import TenantDomainError, TenantDomainService


@pytest.fixture()
def service() -> TenantDomainService:
    return TenantDomainService(AsyncMock())


def test_normalize_hostname_lowercases_and_strips_dot(service: TenantDomainService) -> None:
    assert service.normalize_hostname("Acme.Example.COM.") == "acme.example.com"


@pytest.mark.parametrize(
    "value",
    [
        "https://acme.example.com",
        "acme.example.com/path",
        "acme.example.com:8443",
        "",
        "-bad.example.com",
    ],
)
def test_normalize_hostname_rejects_invalid_input(service: TenantDomainService, value: str) -> None:
    with pytest.raises(TenantDomainError):
        service.normalize_hostname(value)


@pytest.mark.asyncio
async def test_create_domain_rejects_primary_pending_domain(service: TenantDomainService) -> None:
    with pytest.raises(TenantDomainError, match="pending domains cannot be marked as primary"):
        await service.create_domain(
            tenant_id=uuid4(),
            created_by="subject-1",
            hostname="acme.example.com",
            is_primary=True,
        )
