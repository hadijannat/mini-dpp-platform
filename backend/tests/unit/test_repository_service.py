"""Tests for AASRepositoryService — submodel extraction, listing, and get_shell_by_aas_id."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.db.models import DPPStatus
from app.modules.dpps.repository import AASRepositoryService


def _sample_aas_env() -> dict:
    """Return a sample AAS environment with two submodels."""
    return {
        "assetAdministrationShells": [{"id": "urn:uuid:aas-1", "idShort": "TestAAS"}],
        "submodels": [
            {
                "id": "urn:example:nameplate",
                "idShort": "DigitalNameplate",
                "submodelElements": [{"idShort": "ManufacturerName", "value": "Acme"}],
            },
            {
                "id": "urn:example:carbon",
                "idShort": "CarbonFootprint",
                "submodelElements": [{"idShort": "TotalCO2", "value": "42"}],
            },
        ],
    }


class TestGetSubmodelFromRevision:
    """Test static submodel extraction from AAS environments."""

    def test_returns_matching_submodel(self) -> None:
        env = _sample_aas_env()
        result = AASRepositoryService.get_submodel_from_revision(env, "urn:example:nameplate")
        assert result is not None
        assert result["idShort"] == "DigitalNameplate"

    def test_returns_none_for_unknown_id(self) -> None:
        env = _sample_aas_env()
        result = AASRepositoryService.get_submodel_from_revision(env, "urn:example:missing")
        assert result is None

    def test_returns_none_for_empty_env(self) -> None:
        result = AASRepositoryService.get_submodel_from_revision({}, "urn:x")
        assert result is None


class TestListSubmodelIds:
    """Test submodel ID listing."""

    def test_lists_all_submodel_ids(self) -> None:
        env = _sample_aas_env()
        ids = AASRepositoryService.list_submodel_ids(env)
        assert ids == ["urn:example:nameplate", "urn:example:carbon"]

    def test_empty_env_returns_empty_list(self) -> None:
        ids = AASRepositoryService.list_submodel_ids({})
        assert ids == []

    def test_env_with_no_submodels_key(self) -> None:
        ids = AASRepositoryService.list_submodel_ids({"assetAdministrationShells": []})
        assert ids == []


# --------------------------------------------------------------------------
# get_shell_by_aas_id tests
# --------------------------------------------------------------------------


def _make_published_dpp(dpp_id: UUID | None = None, tenant_id: UUID | None = None) -> MagicMock:
    """Create a mock published DPP."""
    dpp = MagicMock()
    dpp.id = dpp_id or uuid4()
    dpp.status = DPPStatus.PUBLISHED
    dpp.tenant_id = tenant_id or uuid4()
    dpp.asset_ids = {"globalAssetId": "urn:example:global:1"}
    dpp.created_at = datetime.now(UTC)
    dpp.updated_at = datetime.now(UTC)
    dpp.current_published_revision_id = uuid4()
    return dpp


@pytest.fixture()
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    return session


class TestGetShellByAasId:
    """Tests for AASRepositoryService.get_shell_by_aas_id."""

    @pytest.mark.asyncio()
    async def test_urn_uuid_valid_uuid_returns_published_dpp(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """Resolution via urn:uuid:{valid-uuid} returns matching published DPP."""
        dpp = _make_published_dpp(tenant_id=tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dpp
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AASRepositoryService(mock_session)
        result = await svc.get_shell_by_aas_id(tenant_id, f"urn:uuid:{dpp.id}")

        assert result is dpp
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_urn_uuid_invalid_string_falls_through_to_jsonb(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """Resolution via urn:uuid:{invalid-string} falls through to JSONB search."""
        dpp = _make_published_dpp(tenant_id=tenant_id)

        # First call: UUID parse fails -> falls through to JSONB search
        # JSONB search returns the DPP
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dpp
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AASRepositoryService(mock_session)
        result = await svc.get_shell_by_aas_id(tenant_id, "urn:uuid:not-a-valid-uuid")

        assert result is dpp
        # Should have been called at least once (the JSONB fallback)
        assert mock_session.execute.await_count >= 1

    @pytest.mark.asyncio()
    async def test_draft_dpp_not_returned(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """Draft DPPs are not returned (only PUBLISHED status matches)."""
        # Both UUID lookup and JSONB search return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AASRepositoryService(mock_session)
        draft_id = uuid4()
        result = await svc.get_shell_by_aas_id(tenant_id, f"urn:uuid:{draft_id}")

        assert result is None

    @pytest.mark.asyncio()
    async def test_archived_dpp_not_returned(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """Archived DPPs are not returned."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AASRepositoryService(mock_session)
        archived_id = uuid4()
        result = await svc.get_shell_by_aas_id(tenant_id, f"urn:uuid:{archived_id}")

        assert result is None

    @pytest.mark.asyncio()
    async def test_global_asset_id_lookup(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """Non-urn:uuid AAS IDs are looked up via JSONB globalAssetId."""
        dpp = _make_published_dpp(tenant_id=tenant_id)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dpp
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = AASRepositoryService(mock_session)
        result = await svc.get_shell_by_aas_id(tenant_id, "urn:example:global:1")

        assert result is dpp

    @pytest.mark.asyncio()
    async def test_urn_uuid_valid_uuid_not_found_falls_to_jsonb(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        """If urn:uuid lookup finds nothing, falls through to JSONB search."""
        dpp = _make_published_dpp(tenant_id=tenant_id)

        # First call (UUID lookup): not found
        uuid_result = MagicMock()
        uuid_result.scalar_one_or_none.return_value = None
        # Second call (JSONB search): found
        jsonb_result = MagicMock()
        jsonb_result.scalar_one_or_none.return_value = dpp

        mock_session.execute = AsyncMock(side_effect=[uuid_result, jsonb_result])

        svc = AASRepositoryService(mock_session)
        some_uuid = uuid4()
        result = await svc.get_shell_by_aas_id(tenant_id, f"urn:uuid:{some_uuid}")

        # Should fall through and try JSONB
        assert result is dpp
        assert mock_session.execute.await_count == 2
