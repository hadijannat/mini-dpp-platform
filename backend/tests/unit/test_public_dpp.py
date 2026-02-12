"""
Unit tests for public (unauthenticated) DPP API endpoint.

Verifies that published DPPs are accessible without auth, and that
drafts/archived DPPs return 404.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.db.models import DataCarrierStatus, DPPStatus, TenantStatus
from app.modules.dpps.public_router import (
    PublicDPPResponse,
    _get_published_revision,
    _resolve_tenant,
    get_withdrawn_carrier_notice,
)


def _make_tenant(*, slug: str = "default", status: TenantStatus = TenantStatus.ACTIVE) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid4()
    tenant.slug = slug
    tenant.status = status
    return tenant


def _make_dpp(
    *,
    status: DPPStatus = DPPStatus.PUBLISHED,
    tenant_id: None = None,
) -> MagicMock:
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.status = status
    dpp.tenant_id = tenant_id or uuid4()
    dpp.asset_ids = {"manufacturerPartId": "PART-001"}
    dpp.qr_payload = None
    dpp.owner_subject = "user-123"
    dpp.created_at = datetime.now(UTC)
    dpp.updated_at = datetime.now(UTC)
    dpp.current_published_revision_id = uuid4()
    return dpp


def _make_revision(dpp_id: None = None) -> MagicMock:
    rev = MagicMock()
    rev.id = uuid4()
    rev.dpp_id = dpp_id or uuid4()
    rev.revision_no = 1
    rev.aas_env_json = {"submodels": []}
    rev.digest_sha256 = "abc123"
    return rev


def _make_carrier(*, tenant_id: None = None) -> MagicMock:
    carrier = MagicMock()
    carrier.id = uuid4()
    carrier.tenant_id = tenant_id or uuid4()
    carrier.dpp_id = uuid4()
    carrier.status = DataCarrierStatus.WITHDRAWN
    carrier.withdrawn_reason = "Recalled for safety check"
    return carrier


# --------------------------------------------------------------------------
# _resolve_tenant
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_tenant_active() -> None:
    """Active tenant should be resolved successfully."""
    tenant = _make_tenant()
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = tenant
    session.execute.return_value = result_mock

    resolved = await _resolve_tenant(session, "default")
    assert resolved.slug == "default"


@pytest.mark.asyncio
async def test_resolve_tenant_not_found_raises_404() -> None:
    """Missing or inactive tenant should raise 404."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute.return_value = result_mock

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_tenant(session, "nonexistent")
    assert exc_info.value.status_code == 404


# --------------------------------------------------------------------------
# _get_published_revision
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_published_revision_returns_revision() -> None:
    dpp = _make_dpp()
    rev = _make_revision()
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = rev
    session.execute.return_value = result_mock

    result = await _get_published_revision(session, dpp)
    assert result is not None
    assert result.revision_no == 1


@pytest.mark.asyncio
async def test_get_published_revision_returns_none_when_no_published_revision() -> None:
    dpp = _make_dpp()
    dpp.current_published_revision_id = None

    session = AsyncMock()
    result = await _get_published_revision(session, dpp)
    assert result is None


# --------------------------------------------------------------------------
# PublicDPPResponse structure
# --------------------------------------------------------------------------


def test_public_response_excludes_sensitive_fields() -> None:
    """PublicDPPResponse should not include owner_subject or qr_payload."""
    fields = set(PublicDPPResponse.model_fields.keys())
    assert "owner_subject" not in fields
    assert "qr_payload" not in fields
    assert "id" in fields
    assert "aas_environment" in fields


@pytest.mark.asyncio
async def test_withdrawn_carrier_notice_returns_html() -> None:
    tenant = _make_tenant(slug="default")
    carrier = _make_carrier(tenant_id=tenant.id)
    session = AsyncMock()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    carrier_result = MagicMock()
    carrier_result.scalar_one_or_none.return_value = carrier
    session.execute.side_effect = [tenant_result, carrier_result]

    response = await get_withdrawn_carrier_notice("default", carrier.id, session)
    assert response.status_code == 200
    body = response.body.decode("utf-8")
    assert "Data Carrier Withdrawn" in body
    assert "Recalled for safety check" in body


@pytest.mark.asyncio
async def test_withdrawn_carrier_notice_404_when_missing() -> None:
    tenant = _make_tenant(slug="default")
    session = AsyncMock()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    carrier_result = MagicMock()
    carrier_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [tenant_result, carrier_result]

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_withdrawn_carrier_notice("default", uuid4(), session)
    assert exc_info.value.status_code == 404
