"""Unit tests for the built-in AAS registry service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.registry.schemas import ShellDescriptorCreate, ShellDescriptorUpdate


@pytest.fixture()
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture()
def created_by() -> str:
    return "test-subject"


@pytest.fixture()
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestBuiltInRegistryService:
    """Tests for BuiltInRegistryService."""

    @pytest.mark.asyncio()
    async def test_create_shell_descriptor(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
        created_by: str,
    ) -> None:
        from app.modules.registry.service import BuiltInRegistryService

        svc = BuiltInRegistryService(mock_session)
        create = ShellDescriptorCreate(
            aas_id="urn:uuid:test-aas-id",
            id_short="TestShell",
            global_asset_id="urn:global:asset",
            specific_asset_ids=[{"name": "partId", "value": "ABC123"}],
            submodel_descriptors=[],
        )

        record = await svc.create_shell_descriptor(tenant_id, create, created_by)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        assert record.aas_id == "urn:uuid:test-aas-id"
        assert record.id_short == "TestShell"
        assert record.global_asset_id == "urn:global:asset"
        assert record.tenant_id == tenant_id
        assert record.created_by_subject == created_by

    @pytest.mark.asyncio()
    async def test_get_shell_descriptor_not_found(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import BuiltInRegistryService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = BuiltInRegistryService(mock_session)
        result = await svc.get_shell_descriptor(tenant_id, "urn:not:found")
        assert result is None

    @pytest.mark.asyncio()
    async def test_delete_shell_descriptor_not_found(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import BuiltInRegistryService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = BuiltInRegistryService(mock_session)
        result = await svc.delete_shell_descriptor(tenant_id, "urn:not:found")
        assert result is False

    @pytest.mark.asyncio()
    async def test_update_shell_descriptor_not_found(
        self,
        mock_session: AsyncMock,
        tenant_id: UUID,
    ) -> None:
        from app.modules.registry.service import BuiltInRegistryService

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        svc = BuiltInRegistryService(mock_session)
        update = ShellDescriptorUpdate(id_short="NewName")
        result = await svc.update_shell_descriptor(tenant_id, "urn:not:found", update)
        assert result is None


class TestShellDescriptorSchemas:
    """Tests for schema validation."""

    def test_create_schema_defaults(self) -> None:
        create = ShellDescriptorCreate(aas_id="urn:test:1")
        assert create.id_short == ""
        assert create.global_asset_id == ""
        assert create.specific_asset_ids == []
        assert create.submodel_descriptors == []
        assert create.dpp_id is None

    def test_update_schema_partial(self) -> None:
        update = ShellDescriptorUpdate(id_short="NewShort")
        assert update.id_short == "NewShort"
        assert update.global_asset_id is None
        assert update.specific_asset_ids is None
