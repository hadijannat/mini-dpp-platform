"""Unit tests for CEN API service lifecycle and immutability behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.db.models import DPPStatus, IdentifierEntityType
from app.modules.cen_api.service import CENAPIConflictError, CENAPIError, CENAPIService
from app.standards.cen_pren.identifiers_18219 import IdentifierGovernanceError


def _mock_dpp(*, status: DPPStatus, asset_ids: dict[str, str]) -> MagicMock:
    dpp = MagicMock()
    dpp.id = uuid4()
    dpp.tenant_id = uuid4()
    dpp.status = status
    dpp.asset_ids = dict(asset_ids)
    dpp.visibility_scope = "owner_team"
    return dpp


def _scalar_list_result(values: list[object]) -> SimpleNamespace:
    return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: values))


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


@pytest.mark.asyncio
async def test_search_dpps_uses_identifier_canonicalization_when_scheme_provided() -> None:
    tenant_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    first = MagicMock(id=first_id, tenant_id=tenant_id)

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            _scalar_list_result([first_id, second_id]),
            _scalar_list_result([first]),
        ]
    )
    service = CENAPIService(session)

    with patch.object(
        service._identifier_service,
        "canonicalize",
        return_value="urn:canonical:1",
    ) as canonicalize_mock:
        rows, next_cursor = await service.search_dpps(
            tenant_id=tenant_id,
            limit=1,
            cursor=None,
            identifier="raw-id",
            scheme="uri",
            status=None,
        )

    assert rows == [first]
    assert next_cursor is not None
    canonicalize_mock.assert_called_once_with(scheme_code="uri", value_raw="raw-id")


@pytest.mark.asyncio
async def test_search_dpps_raises_when_identifier_canonicalization_fails() -> None:
    session = AsyncMock()
    session.execute = AsyncMock()
    service = CENAPIService(session)

    with (
        patch.object(
            service._identifier_service,
            "canonicalize",
            side_effect=IdentifierGovernanceError("invalid identifier"),
        ),
        pytest.raises(CENAPIError, match="invalid identifier"),
    ):
        await service.search_dpps(
            tenant_id=uuid4(),
            limit=10,
            cursor=None,
            identifier="::bad::",
            scheme="uri",
            status=None,
        )

    session.execute.assert_not_called()
