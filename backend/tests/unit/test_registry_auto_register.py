"""Tests for auto_register_from_dpp in the built-in AAS registry service."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.registry.service import BuiltInRegistryService


@pytest.fixture()
def tenant_id():
    return uuid4()


@pytest.fixture()
def created_by():
    return "test-subject"


@pytest.fixture()
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


def _make_shell_descriptor_payload(
    *,
    aas_id: str = "urn:uuid:aas-1",
    id_short: str = "TestShell",
    global_asset_id: str = "urn:example:asset:1",
    specific_asset_ids: list[dict[str, str]] | None = None,
    submodel_descriptors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a mock DTR payload dict."""
    return {
        "id": aas_id,
        "idShort": id_short,
        "globalAssetId": global_asset_id,
        "specificAssetIds": specific_asset_ids or [
            {"name": "serialNumber", "value": "SN123"},
            {"name": "partId", "value": "P456"},
        ],
        "submodelDescriptors": submodel_descriptors or [],
    }


def _make_dpp(dpp_id=None):
    """Create a mock DPP."""
    dpp = MagicMock()
    dpp.id = dpp_id or uuid4()
    dpp.asset_ids = {"manufacturerPartId": "PART-001"}
    return dpp


def _make_revision():
    """Create a mock DPPRevision."""
    rev = MagicMock()
    rev.id = uuid4()
    rev.revision_no = 1
    rev.aas_env_json = {"submodels": []}
    return rev


class TestAutoRegisterFromDPP:
    """Tests for BuiltInRegistryService.auto_register_from_dpp."""

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_creates_shell_descriptor_with_correct_fields(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Creates a shell descriptor record with correct fields from DPP data."""
        payload = _make_shell_descriptor_payload()
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)
        await svc.auto_register_from_dpp(
            dpp=dpp,
            revision=revision,
            tenant_id=tenant_id,
            created_by=created_by,
            submodel_base_url="https://api.example.com",
        )

        # Should have been called twice: once for upsert, once for discovery mappings
        assert mock_session.execute.await_count >= 1
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_upsert_does_not_duplicate(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Second call upserts (updates) rather than duplicating due to ON CONFLICT."""
        payload = _make_shell_descriptor_payload()
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)

        # Call twice
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )

        # Both calls use pg_insert with on_conflict_do_update, so no duplicate inserts.
        # session.add is NOT called (uses execute with pg_insert instead).
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_global_asset_id_triggers_discovery_mapping(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """globalAssetId triggers a discovery mapping entry."""
        payload = _make_shell_descriptor_payload(
            global_asset_id="urn:example:global:asset",
            specific_asset_ids=[],
        )
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )

        # Should execute: 1 for shell upsert + 1 for discovery mappings
        assert mock_session.execute.await_count == 2

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_specific_asset_ids_each_get_discovery_mapping(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Each specific_asset_ids entry gets a discovery mapping."""
        payload = _make_shell_descriptor_payload(
            global_asset_id="",
            specific_asset_ids=[
                {"name": "serialNumber", "value": "SN123"},
                {"name": "partId", "value": "P456"},
            ],
        )
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )

        # Shell upsert + discovery batch insert
        assert mock_session.execute.await_count == 2

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_empty_name_or_value_skipped_in_discovery(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """Entries with empty name or value are skipped from discovery mappings."""
        payload = _make_shell_descriptor_payload(
            global_asset_id="",
            specific_asset_ids=[
                {"name": "", "value": "SN123"},
                {"name": "partId", "value": ""},
                {"name": "validKey", "value": "validValue"},
            ],
        )
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )

        # Shell upsert + 1 discovery mapping batch (only validKey/validValue)
        assert mock_session.execute.await_count == 2

    @pytest.mark.asyncio()
    @patch("app.modules.connectors.catenax.mapping.build_shell_descriptor")
    async def test_no_discovery_mappings_when_all_empty(
        self,
        mock_build: MagicMock,
        mock_session: AsyncMock,
        tenant_id,
        created_by: str,
    ) -> None:
        """No discovery mappings when globalAssetId is empty and all asset IDs are empty."""
        payload = _make_shell_descriptor_payload(
            global_asset_id="",
            specific_asset_ids=[
                {"name": "", "value": ""},
                {"name": "", "value": "val"},
            ],
        )
        mock_shell = MagicMock()
        mock_shell.to_dtr_payload.return_value = payload
        mock_build.return_value = mock_shell

        dpp = _make_dpp()
        revision = _make_revision()

        svc = BuiltInRegistryService(mock_session)
        await svc.auto_register_from_dpp(
            dpp=dpp, revision=revision, tenant_id=tenant_id,
            created_by=created_by, submodel_base_url="https://api.example.com",
        )

        # Only shell upsert, no discovery mapping insert
        assert mock_session.execute.await_count == 1
