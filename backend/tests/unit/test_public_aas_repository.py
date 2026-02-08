"""Tests for public AAS Repository endpoints in dpps/public_router.py.

Covers: _decode_b64, shell endpoint with ESPR tier filtering,
submodel endpoint 404 on tier filtering, submodel $value endpoint,
and 404 scenarios for invalid tenant/DPP/revision/submodel.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.models import DPPStatus, TenantStatus
from app.modules.dpps.public_router import _decode_b64

# ======================================================================
# _decode_b64 tests
# ======================================================================


class TestDecodeB64:
    """Tests for the _decode_b64 helper function."""

    def test_valid_base64url(self) -> None:
        """Standard base64url-encoded string is decoded correctly."""
        original = "urn:uuid:abc-123"
        encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")
        result = _decode_b64(encoded)
        assert result == original

    def test_valid_base64url_with_padding(self) -> None:
        """base64url with existing padding is handled correctly."""
        original = "test-value"
        encoded = base64.urlsafe_b64encode(original.encode()).decode()
        result = _decode_b64(encoded)
        assert result == original

    def test_invalid_bytes_raises_400(self) -> None:
        """Invalid base64 bytes raise 400."""
        with pytest.raises(HTTPException) as exc_info:
            _decode_b64("!!!invalid-not-base64!!!")
        assert exc_info.value.status_code == 400
        assert "Invalid base64url" in exc_info.value.detail

    def test_missing_padding_handled(self) -> None:
        """Missing padding is automatically added."""
        original = "urn:example:submodel:1"
        encoded = base64.urlsafe_b64encode(original.encode()).decode()
        # Remove padding
        encoded_no_pad = encoded.rstrip("=")
        result = _decode_b64(encoded_no_pad)
        assert result == original


# ======================================================================
# Helpers
# ======================================================================


def _make_tenant(*, slug: str = "default", status: TenantStatus = TenantStatus.ACTIVE):
    tenant = MagicMock()
    tenant.id = uuid4()
    tenant.slug = slug
    tenant.status = status
    return tenant


def _make_dpp(*, status: DPPStatus = DPPStatus.PUBLISHED, tenant_id=None):
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.status = status
    dpp.tenant_id = tenant_id or uuid4()
    dpp.asset_ids = {"manufacturerPartId": "PART-001"}
    dpp.created_at = datetime.now(UTC)
    dpp.updated_at = datetime.now(UTC)
    dpp.current_published_revision_id = uuid4()
    return dpp


def _make_revision(*, submodels: list[dict[str, Any]] | None = None):
    rev = MagicMock()
    rev.id = uuid4()
    rev.revision_no = 1
    rev.aas_env_json = {
        "assetAdministrationShells": [],
        "submodels": submodels
        or [
            {
                "id": "urn:example:nameplate",
                "idShort": "DigitalNameplate",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {"type": "Submodel", "value": "https://admin-shell.io/zvei/nameplate/V1.0"}
                    ],
                },
                "submodelElements": [{"idShort": "ManufacturerName", "value": "Acme"}],
            },
            {
                "id": "urn:example:internal",
                "idShort": "InternalData",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [
                        {"type": "Submodel", "value": "https://example.com/internal/secret/V1.0"}
                    ],
                },
                "submodelElements": [{"idShort": "Secret", "value": "hidden"}],
            },
        ],
    }
    rev.digest_sha256 = "abc123"
    return rev


def _encode_b64(s: str) -> str:
    """Encode a string to base64url without padding."""
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


# ======================================================================
# Shell endpoint with ESPR tier filtering
# ======================================================================


class TestShellEndpointWithTier:
    """Tests for the shell endpoint with espr_tier query parameter."""

    @pytest.mark.asyncio()
    async def test_shell_filters_env_for_consumer_tier(self) -> None:
        """Shell endpoint returns filtered environment when espr_tier=consumer."""
        from app.modules.dpps.public_router import get_shell_by_aas_id

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        revision = _make_revision()

        db = AsyncMock()
        # First call: _resolve_tenant
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        # Second call: repo.get_shell_by_aas_id
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp
        # Third call: repo.get_published_revision
        rev_result = MagicMock()
        rev_result.scalar_one_or_none.return_value = revision

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result, rev_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")

        response = await get_shell_by_aas_id(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            db=db,
            espr_tier="consumer",
        )

        # Consumer tier should see nameplate but not the internal submodel
        assert response.aas_environment is not None
        submodel_ids = [sm["id"] for sm in response.aas_environment.get("submodels", [])]
        assert "urn:example:nameplate" in submodel_ids
        assert "urn:example:internal" not in submodel_ids

    @pytest.mark.asyncio()
    async def test_shell_returns_all_for_manufacturer_tier(self) -> None:
        """Shell endpoint returns all submodels for manufacturer tier."""
        from app.modules.dpps.public_router import get_shell_by_aas_id

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        revision = _make_revision()

        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp
        rev_result = MagicMock()
        rev_result.scalar_one_or_none.return_value = revision

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result, rev_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")

        response = await get_shell_by_aas_id(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            db=db,
            espr_tier="manufacturer",
        )

        assert response.aas_environment is not None
        assert len(response.aas_environment.get("submodels", [])) == 2


# ======================================================================
# Submodel endpoint -- 404 when tier hides submodel
# ======================================================================


class TestSubmodelEndpointTierFiltering:
    """Submodel endpoint returns 404 when tier filtering hides the submodel."""

    @pytest.mark.asyncio()
    async def test_submodel_404_when_tier_hides_it(self) -> None:
        """Submodel endpoint returns 404 when the requested submodel is hidden by tier."""
        from app.modules.dpps.public_router import get_submodel_by_id

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        revision = _make_revision()

        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp
        rev_result = MagicMock()
        rev_result.scalar_one_or_none.return_value = revision

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result, rev_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")
        submodel_id_b64 = _encode_b64("urn:example:internal")

        with pytest.raises(HTTPException) as exc_info:
            await get_submodel_by_id(
                tenant_slug="default",
                aas_id_b64=aas_id_b64,
                submodel_id_b64=submodel_id_b64,
                db=db,
                espr_tier="consumer",
            )
        assert exc_info.value.status_code == 404
        assert "Submodel not found" in exc_info.value.detail


# ======================================================================
# Submodel $value endpoint
# ======================================================================


class TestSubmodelValueEndpoint:
    """Submodel $value endpoint returns only submodelElements."""

    @pytest.mark.asyncio()
    async def test_value_returns_only_submodel_elements(self) -> None:
        from app.modules.dpps.public_router import get_submodel_value

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        revision = _make_revision()

        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp
        rev_result = MagicMock()
        rev_result.scalar_one_or_none.return_value = revision

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result, rev_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")
        submodel_id_b64 = _encode_b64("urn:example:nameplate")

        result = await get_submodel_value(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            submodel_id_b64=submodel_id_b64,
            db=db,
            espr_tier=None,
        )

        assert "submodelElements" in result
        assert len(result["submodelElements"]) == 1
        assert result["submodelElements"][0]["idShort"] == "ManufacturerName"
        # Should NOT contain other submodel keys
        assert "id" not in result
        assert "idShort" not in result
        assert "semanticId" not in result


# ======================================================================
# 404 scenarios
# ======================================================================


class TestPublicAAS404Scenarios:
    """404 for invalid tenant, DPP not found, no revision, submodel not found."""

    @pytest.mark.asyncio()
    async def test_invalid_tenant_404(self) -> None:
        """Invalid tenant slug returns 404."""
        from app.modules.dpps.public_router import get_shell_by_aas_id

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        aas_id_b64 = _encode_b64("urn:uuid:any")

        with pytest.raises(HTTPException) as exc_info:
            await get_shell_by_aas_id(
                tenant_slug="nonexistent",
                aas_id_b64=aas_id_b64,
                db=db,
                espr_tier=None,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio()
    async def test_dpp_not_found_404(self) -> None:
        """Published DPP not found returns 404."""
        from app.modules.dpps.public_router import get_shell_by_aas_id

        tenant = _make_tenant()
        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        # DPP lookup returns None
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result])

        aas_id_b64 = _encode_b64("urn:uuid:missing-dpp")

        with pytest.raises(HTTPException) as exc_info:
            await get_shell_by_aas_id(
                tenant_slug="default",
                aas_id_b64=aas_id_b64,
                db=db,
                espr_tier=None,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio()
    async def test_no_revision_submodel_endpoint_404(self) -> None:
        """Submodel endpoint returns 404 when DPP has no revision."""
        from app.modules.dpps.public_router import get_submodel_by_id

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        dpp.current_published_revision_id = None  # No revision

        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")
        submodel_id_b64 = _encode_b64("urn:example:nameplate")

        with pytest.raises(HTTPException) as exc_info:
            await get_submodel_by_id(
                tenant_slug="default",
                aas_id_b64=aas_id_b64,
                submodel_id_b64=submodel_id_b64,
                db=db,
                espr_tier=None,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio()
    async def test_submodel_not_found_404(self) -> None:
        """Submodel endpoint returns 404 when requested submodel ID does not exist."""
        from app.modules.dpps.public_router import get_submodel_by_id

        tenant = _make_tenant()
        dpp = _make_dpp(tenant_id=tenant.id)
        revision = _make_revision()

        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = dpp
        rev_result = MagicMock()
        rev_result.scalar_one_or_none.return_value = revision

        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result, rev_result])

        aas_id_b64 = _encode_b64(f"urn:uuid:{dpp.id}")
        submodel_id_b64 = _encode_b64("urn:example:does-not-exist")

        with pytest.raises(HTTPException) as exc_info:
            await get_submodel_by_id(
                tenant_slug="default",
                aas_id_b64=aas_id_b64,
                submodel_id_b64=submodel_id_b64,
                db=db,
                espr_tier=None,
            )
        assert exc_info.value.status_code == 404
        assert "Submodel not found" in exc_info.value.detail
