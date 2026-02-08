"""Tests for IDTA 01002-3-0 API profile: schemas, pagination, endpoints."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.db.models import DPPStatus, TenantStatus
from app.modules.dpps.idta_schemas import (
    IDTAMessage,
    IDTAResult,
    PagedResult,
    PagingMetadata,
    ServiceDescription,
    decode_cursor,
    encode_cursor,
)

# ======================================================================
# Schema serialization tests
# ======================================================================


class TestIDTASchemas:
    """Test IDTA standard Pydantic model serialization."""

    def test_idta_message_camel_case(self) -> None:
        """IDTAMessage serializes to camelCase via aliases."""
        msg = IDTAMessage(
            code="42",
            correlation_id="req-001",
            message_type="Error",
            text="Not found",
            timestamp="2026-01-01T00:00:00Z",
        )
        data = msg.model_dump(by_alias=True)
        assert "correlationId" in data
        assert "messageType" in data
        assert data["correlationId"] == "req-001"
        assert data["messageType"] == "Error"

    def test_idta_message_snake_case(self) -> None:
        """IDTAMessage can serialize with snake_case field names."""
        msg = IDTAMessage(
            code="42",
            message_type="Info",
            text="ok",
            timestamp="2026-01-01T00:00:00Z",
        )
        data = msg.model_dump()
        assert "correlation_id" in data
        assert "message_type" in data

    def test_idta_result_default_messages(self) -> None:
        """IDTAResult has empty messages list by default."""
        result = IDTAResult()
        assert result.messages == []

    def test_paging_metadata_default_none(self) -> None:
        """PagingMetadata cursor defaults to None."""
        meta = PagingMetadata()
        assert meta.cursor is None

    def test_paged_result_serialization(self) -> None:
        """PagedResult serializes with camelCase paging key."""
        paged = PagedResult[str](
            result=["a", "b"],
            paging_metadata=PagingMetadata(cursor="abc123"),
        )
        data = paged.model_dump(by_alias=True)
        assert data["result"] == ["a", "b"]
        assert "pagingMetadata" in data
        assert data["pagingMetadata"]["cursor"] == "abc123"

    def test_paged_result_empty(self) -> None:
        """PagedResult handles empty results with no cursor."""
        paged = PagedResult[int](
            result=[],
            paging_metadata=PagingMetadata(),
        )
        data = paged.model_dump(by_alias=True)
        assert data["result"] == []
        assert data["pagingMetadata"]["cursor"] is None

    def test_service_description(self) -> None:
        """ServiceDescription contains expected profiles."""
        desc = ServiceDescription(profiles=["https://example.com/profile"])
        assert len(desc.profiles) == 1
        assert desc.profiles[0] == "https://example.com/profile"


# ======================================================================
# Cursor encode/decode tests
# ======================================================================


class TestCursorHelpers:
    """Test base64url cursor encoding and decoding."""

    def test_roundtrip(self) -> None:
        """Encoding then decoding returns the same UUID."""
        uid = uuid4()
        encoded = encode_cursor(uid)
        decoded = decode_cursor(encoded)
        assert decoded == uid

    def test_encode_is_url_safe(self) -> None:
        """Encoded cursor has no padding or unsafe characters."""
        uid = uuid4()
        encoded = encode_cursor(uid)
        assert "=" not in encoded
        assert "+" not in encoded
        assert "/" not in encoded

    def test_decode_invalid_raises_400(self) -> None:
        """Decoding invalid cursor raises HTTPException(400)."""
        with pytest.raises(HTTPException) as exc_info:
            decode_cursor("not-valid-base64-uuid")
        assert exc_info.value.status_code == 400

    def test_decode_short_base64_raises_400(self) -> None:
        """Decoding valid base64 but wrong length raises HTTPException(400)."""
        with pytest.raises(HTTPException) as exc_info:
            decode_cursor("AAAA")
        assert exc_info.value.status_code == 400

    def test_different_uuids_produce_different_cursors(self) -> None:
        """Different UUIDs produce different cursors."""
        a = encode_cursor(uuid4())
        b = encode_cursor(uuid4())
        assert a != b


# ======================================================================
# Helpers
# ======================================================================


def _make_tenant(
    *,
    slug: str = "default",
    status: TenantStatus = TenantStatus.ACTIVE,
) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid4()
    tenant.slug = slug
    tenant.status = status
    return tenant


def _make_dpp(
    *,
    status: DPPStatus = DPPStatus.PUBLISHED,
    tenant_id: UUID | None = None,
) -> MagicMock:
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.status = status
    dpp.tenant_id = tenant_id or uuid4()
    dpp.asset_ids = {"manufacturerPartId": "PART-001"}
    dpp.created_at = datetime.now(UTC)
    dpp.updated_at = datetime.now(UTC)
    dpp.current_published_revision_id = uuid4()
    return dpp


def _make_revision(
    *,
    submodels: list[dict[str, Any]] | None = None,
) -> MagicMock:
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
                        {
                            "type": "Submodel",
                            "value": ("https://admin-shell.io/zvei/nameplate/V1.0"),
                        }
                    ],
                },
                "submodelElements": [{"idShort": "ManufacturerName", "value": "Acme"}],
            },
        ],
    }
    rev.digest_sha256 = "abc123"
    return rev


def _encode_b64(s: str) -> str:
    """Encode a string to base64url without padding."""
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


# ======================================================================
# ServiceDescription endpoint
# ======================================================================


class TestServiceDescriptionEndpoint:
    """Tests for GET /{tenant}/service-description."""

    @pytest.mark.asyncio()
    async def test_returns_profiles(self) -> None:
        from app.modules.dpps.public_router import get_service_description

        tenant = _make_tenant()
        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        db.execute = AsyncMock(return_value=tenant_result)

        result = await get_service_description(tenant_slug="default", db=db)

        assert isinstance(result, ServiceDescription)
        assert len(result.profiles) == 1
        assert "SSP-002" in result.profiles[0]

    @pytest.mark.asyncio()
    async def test_invalid_tenant_404(self) -> None:
        from app.modules.dpps.public_router import get_service_description

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await get_service_description(tenant_slug="nonexistent", db=db)
        assert exc_info.value.status_code == 404


# ======================================================================
# ?content=value query parameter
# ======================================================================


class TestContentValueQueryParam:
    """Tests for ?content=value on submodel endpoint."""

    @pytest.mark.asyncio()
    async def test_content_normal_returns_full(self) -> None:
        """content=normal returns the full submodel."""
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
        sm_id_b64 = _encode_b64("urn:example:nameplate")

        result = await get_submodel_by_id(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            submodel_id_b64=sm_id_b64,
            db=db,
            espr_tier=None,
            content="normal",
        )

        assert "id" in result
        assert "submodelElements" in result

    @pytest.mark.asyncio()
    async def test_content_value_returns_elements_only(self) -> None:
        """content=value returns only submodelElements."""
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
        sm_id_b64 = _encode_b64("urn:example:nameplate")

        result = await get_submodel_by_id(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            submodel_id_b64=sm_id_b64,
            db=db,
            espr_tier=None,
            content="value",
        )

        assert "submodelElements" in result
        assert "id" not in result
        assert "idShort" not in result


# ======================================================================
# Submodel refs listing
# ======================================================================


class TestListSubmodelRefs:
    """Tests for GET /{tenant}/shells/{b64}/submodels."""

    @pytest.mark.asyncio()
    async def test_returns_refs_with_semantic_id(self) -> None:
        from app.modules.dpps.public_router import list_submodel_refs

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

        refs = await list_submodel_refs(
            tenant_slug="default",
            aas_id_b64=aas_id_b64,
            db=db,
            espr_tier=None,
        )

        assert len(refs) == 1
        assert refs[0]["id"] == "urn:example:nameplate"
        assert "semanticId" in refs[0]

    @pytest.mark.asyncio()
    async def test_404_when_dpp_not_found(self) -> None:
        from app.modules.dpps.public_router import list_submodel_refs

        tenant = _make_tenant()
        db = AsyncMock()
        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none.return_value = tenant
        dpp_result = MagicMock()
        dpp_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(side_effect=[tenant_result, dpp_result])

        aas_id_b64 = _encode_b64("urn:uuid:missing")

        with pytest.raises(HTTPException) as exc_info:
            await list_submodel_refs(
                tenant_slug="default",
                aas_id_b64=aas_id_b64,
                db=db,
                espr_tier=None,
            )
        assert exc_info.value.status_code == 404
