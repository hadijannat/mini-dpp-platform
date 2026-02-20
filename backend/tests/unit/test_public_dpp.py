"""
Unit tests for public (unauthenticated) DPP API endpoint.

Verifies that published DPPs are accessible without auth, and that
drafts/archived DPPs return 404.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest

from app.db.models import DataCarrierStatus, DPPStatus, TenantStatus
from app.modules.dpps.public_router import (
    PublicDPPResponse,
    _get_published_revision,
    _resolve_tenant,
    get_public_dpp_integrity_bundle,
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
    rev.digest_algorithm = "sha-256"
    rev.digest_canonicalization = "rfc8785"
    rev.signed_jws = jwt.encode(
        {"sub": "test"},
        "0123456789abcdef0123456789abcdef",
        algorithm="HS256",
        headers={"kid": "dpp-signing-kid"},
    )
    return rev


def _make_carrier(*, tenant_id: None = None) -> MagicMock:
    carrier = MagicMock()
    carrier.id = uuid4()
    carrier.tenant_id = tenant_id or uuid4()
    carrier.dpp_id = uuid4()
    carrier.status = DataCarrierStatus.WITHDRAWN
    carrier.withdrawn_reason = "Recalled for safety check"
    return carrier


def _make_anchor(*, tenant_id: None = None) -> MagicMock:
    anchor = MagicMock()
    anchor.id = uuid4()
    anchor.tenant_id = tenant_id or uuid4()
    anchor.root_hash = "f" * 64
    anchor.first_sequence = 10
    anchor.last_sequence = 20
    anchor.created_at = datetime.now(UTC)
    anchor.signature_kid = "audit-signing-kid"
    anchor.tsa_token = b"tsa-token"
    return anchor


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


@pytest.mark.asyncio
@patch("app.modules.dpps.public_router.get_settings")
async def test_integrity_bundle_includes_crypto_metadata_and_anchor(
    mock_settings: MagicMock,
) -> None:
    tenant = _make_tenant(slug="default")
    dpp = _make_dpp(tenant_id=tenant.id)
    revision = _make_revision(dpp.id)
    revision.tenant_id = tenant.id
    dpp.current_published_revision_id = revision.id
    anchor = _make_anchor(tenant_id=tenant.id)

    settings = MagicMock()
    settings.api_v1_prefix = "/api/v1"
    mock_settings.return_value = settings

    session = AsyncMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    dpp_result = MagicMock()
    dpp_result.scalar_one_or_none.return_value = dpp
    revision_result = MagicMock()
    revision_result.scalar_one_or_none.return_value = revision
    anchor_result = MagicMock()
    anchor_result.scalar_one_or_none.return_value = anchor
    session.execute.side_effect = [tenant_result, dpp_result, revision_result, anchor_result]

    response = await get_public_dpp_integrity_bundle("default", dpp.id, session)
    payload = response.model_dump(by_alias=True)

    assert payload["dpp_id"] == dpp.id
    assert payload["revision_id"] == revision.id
    assert payload["digest_sha256"] == "abc123"
    assert payload["digestAlgorithm"] == "sha-256"
    assert payload["digestCanonicalization"] == "rfc8785"
    assert payload["signatureKid"] == "dpp-signing-kid"
    assert payload["verificationMethodUrls"] == [
        "/api/v1/public/default/.well-known/did.json",
        "/api/v1/public/.well-known/jwks.json",
    ]
    assert payload["anchor"]["anchor_id"] == anchor.id
    assert payload["anchor"]["signatureKid"] == "audit-signing-kid"
    assert payload["anchor"]["tsaTokenPresent"] is True


@pytest.mark.asyncio
async def test_integrity_bundle_404_when_dpp_not_found() -> None:
    tenant = _make_tenant(slug="default")
    session = AsyncMock()

    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    dpp_result = MagicMock()
    dpp_result.scalar_one_or_none.return_value = None
    session.execute.side_effect = [tenant_result, dpp_result]

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_public_dpp_integrity_bundle("default", uuid4(), session)
    assert exc_info.value.status_code == 404
