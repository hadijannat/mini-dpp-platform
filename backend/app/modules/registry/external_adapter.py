"""BaSyx V2 external registry adapter implementing the RegistryClient protocol."""

from __future__ import annotations

import base64
import json
from typing import Any, cast

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class BasyxV2RegistryAdapter:
    """Adapter for an external BaSyx V2 AAS Registry.

    Implements the ``RegistryClient`` protocol defined in
    ``app.modules.connectors.registry.base``.
    """

    def __init__(
        self,
        base_url: str,
        discovery_url: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._discovery_url = discovery_url.rstrip("/") if discovery_url else None
        self._client: httpx.AsyncClient | None = None

    def _encode_id(self, aas_id: str) -> str:
        """Base64-URL-safe encode an AAS ID for path parameters."""
        return base64.urlsafe_b64encode(aas_id.encode()).decode().rstrip("=")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
            )
        return self._client

    async def register_shell(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        """Register a new shell descriptor in the external registry."""
        client = await self._get_client()
        response = await client.post("/shell-descriptors", json=descriptor)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def update_shell(
        self,
        shell_id: str,
        descriptor: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing shell descriptor."""
        client = await self._get_client()
        encoded_id = self._encode_id(shell_id)
        response = await client.put(
            f"/shell-descriptors/{encoded_id}",
            json=descriptor,
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())

    async def get_shell(self, shell_id: str) -> dict[str, Any] | None:
        """Retrieve a shell descriptor by ID. Returns None if not found."""
        client = await self._get_client()
        encoded_id = self._encode_id(shell_id)
        try:
            response = await client.get(f"/shell-descriptors/{encoded_id}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete_shell(self, shell_id: str) -> None:
        """Delete a shell descriptor from the external registry."""
        client = await self._get_client()
        encoded_id = self._encode_id(shell_id)
        response = await client.delete(f"/shell-descriptors/{encoded_id}")
        if response.status_code not in (200, 204, 404):
            response.raise_for_status()

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity to the external registry."""
        try:
            client = await self._get_client()
            response = await client.get("/shell-descriptors", params={"limit": 1})
            response.raise_for_status()
            return {
                "status": "connected",
                "registry_url": self._base_url,
            }
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "error_code": e.response.status_code,
                "error_message": str(e),
            }
        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e),
            }

    async def lookup_discovery(
        self,
        asset_id_key: str,
        asset_id_value: str,
    ) -> list[str]:
        """Look up AAS IDs via the external discovery endpoint (if configured)."""
        if not self._discovery_url:
            return []
        async with httpx.AsyncClient(base_url=self._discovery_url, timeout=30.0) as client:
            response = await client.get(
                "/lookup/shells",
                params={"assetIds": json.dumps({"name": asset_id_key, "value": asset_id_value})},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [str(item) for item in data]
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
