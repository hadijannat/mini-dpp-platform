"""Unit tests for the asset discovery service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest


@pytest.fixture()
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestDiscoveryService:
    """Tests for DiscoveryService."""

    @pytest.mark.asyncio()
    async def test_create_mapping(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import DiscoveryService

        svc = DiscoveryService(mock_session)
        mapping = await svc.create_mapping(
            tenant_id=tenant_id,
            asset_id_key="serialNumber",
            asset_id_value="SN12345",
            aas_id="urn:uuid:test-aas",
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert mapping.asset_id_key == "serialNumber"
        assert mapping.asset_id_value == "SN12345"
        assert mapping.aas_id == "urn:uuid:test-aas"
        assert mapping.tenant_id == tenant_id

    @pytest.mark.asyncio()
    async def test_lookup_returns_aas_ids(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import DiscoveryService

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            "urn:uuid:aas-1",
            "urn:uuid:aas-2",
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = DiscoveryService(mock_session)
        result = await svc.lookup(tenant_id, "partId", "P123")

        assert result == ["urn:uuid:aas-1", "urn:uuid:aas-2"]

    @pytest.mark.asyncio()
    async def test_delete_mapping_not_found(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import DiscoveryService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = DiscoveryService(mock_session)
        result = await svc.delete_mapping(tenant_id, "partId", "P123", "urn:uuid:not-exist")
        assert result is False

    @pytest.mark.asyncio()
    async def test_list_mappings_empty(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import DiscoveryService

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = DiscoveryService(mock_session)
        result = await svc.list_mappings(tenant_id)
        assert result == []


class TestDiscoveryReexport:
    """Test that the discovery module re-exports correctly."""

    def test_import_from_discovery_module(self) -> None:
        from app.modules.registry.discovery import DiscoveryService as DS

        assert DS is not None
