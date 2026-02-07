"""Catena-X DTR adapter implementing the ``RegistryClient`` protocol.

Wraps the existing :class:`DTRClient` to conform to the unified
registry interface, translating between dict-based descriptors and
the DTRClient's ``ShellDescriptor`` dataclass.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.modules.connectors.catenax.dtr_client import (
    DTRClient,
    DTRConfig,
    ShellDescriptor,
)

logger = get_logger(__name__)


class CatenaXRegistryAdapter:
    """``RegistryClient`` adapter wrapping the Catena-X DTRClient."""

    def __init__(self, config: DTRConfig) -> None:
        self._client = DTRClient(config)

    async def register_shell(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        """Register a shell descriptor via the Catena-X DTR."""
        shell = _dict_to_shell_descriptor(descriptor)
        return await self._client.register_shell(shell)

    async def update_shell(self, shell_id: str, descriptor: dict[str, Any]) -> dict[str, Any]:
        """Update a shell descriptor in the Catena-X DTR."""
        shell = _dict_to_shell_descriptor(descriptor)
        return await self._client.update_shell(shell_id, shell)

    async def get_shell(self, shell_id: str) -> dict[str, Any] | None:
        """Retrieve a shell descriptor from the Catena-X DTR."""
        return await self._client.get_shell(shell_id)

    async def delete_shell(self, shell_id: str) -> None:
        """Delete a shell descriptor from the Catena-X DTR."""
        await self._client.delete_shell(shell_id)

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity to the Catena-X DTR."""
        return await self._client.test_connection()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


def _dict_to_shell_descriptor(data: dict[str, Any]) -> ShellDescriptor:
    """Convert a dict to a ``ShellDescriptor`` dataclass."""
    return ShellDescriptor(
        id=str(data.get("id", "")),
        id_short=str(data.get("idShort", "")),
        global_asset_id=str(data.get("globalAssetId", "")),
        specific_asset_ids=data.get("specificAssetIds", []),
        submodel_descriptors=data.get("submodelDescriptors", []),
    )
