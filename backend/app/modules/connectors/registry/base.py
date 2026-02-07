"""Abstract protocol for DTR registry clients.

Defines the ``RegistryClient`` protocol that all registry adapters must
implement, enabling the platform to work with different AAS registries
(Catena-X DTR, BaSyx Registry, etc.) through a unified interface.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RegistryClient(Protocol):
    """Protocol for AAS shell descriptor registry operations."""

    async def register_shell(
        self, descriptor: dict[str, Any]
    ) -> dict[str, Any]:
        """Register a new shell descriptor in the registry."""
        ...

    async def update_shell(
        self, shell_id: str, descriptor: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing shell descriptor."""
        ...

    async def get_shell(self, shell_id: str) -> dict[str, Any] | None:
        """Retrieve a shell descriptor by ID. Returns None if not found."""
        ...

    async def delete_shell(self, shell_id: str) -> None:
        """Delete a shell descriptor from the registry."""
        ...

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity and authentication to the registry."""
        ...
