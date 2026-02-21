"""Unit tests for CEN API service lifecycle and immutability behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import DPPStatus, IdentifierEntityType
from app.modules.cen_api.service import CENAPIConflictError, CENAPIError, CENAPIService


def _mock_dpp(*, status: DPPStatus, asset_ids: dict[str, str]) -> MagicMock:
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.tenant_id = uuid4()
    dpp.status = status
    dpp.asset_ids = dict(asset_ids)
    dpp.visibility_scope = "owner_team"
    return dpp


@pytest.mark.asyncio
async def test_update_published_dpp_identifier_fields_requires_supersede() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    service = CENAPIService(session)
    service._settings.cen_dpp_enabled = False
    dpp = _mock_dpp(status=DPPStatus.PUBLISHED, asset_ids={"gtin": "01234567890128"})

    with (
        patch.object(service, "get_dpp", AsyncMock(return_value=dpp)),
        pytest.raises(CENAPIConflictError),
    ):
        await service.update_dpp(
            tenant_id=dpp.tenant_id,
            dpp_id=dpp.id,
            updated_by="publisher-sub",
            asset_ids_patch={"gtin": "01234567890129"},
            visibility_scope=None,
        )


@pytest.mark.asyncio
async def test_update_draft_dpp_allows_identifier_change() -> None:
    session = AsyncMock()
    session.flush = AsyncMock()
    service = CENAPIService(session)
    service._settings.cen_dpp_enabled = False
    dpp = _mock_dpp(status=DPPStatus.DRAFT, asset_ids={"gtin": "01234567890128"})

    with patch.object(service, "get_dpp", AsyncMock(return_value=dpp)):
        updated = await service.update_dpp(
            tenant_id=dpp.tenant_id,
            dpp_id=dpp.id,
            updated_by="publisher-sub",
            asset_ids_patch={"gtin": "01234567890129"},
            visibility_scope=None,
        )

    assert updated.asset_ids["gtin"] == "01234567890129"


@pytest.mark.asyncio
async def test_validate_identifier_wraps_governance_errors() -> None:
    session = AsyncMock()
    service = CENAPIService(session)
    service._identifier_service._settings.cen_allow_http_identifiers = False

    with pytest.raises(CENAPIError):
        await service.validate_identifier(
            entity_type=IdentifierEntityType.PRODUCT,
            scheme_code="uri",
            value_raw="http://example.com/id",
            granularity=None,
        )
