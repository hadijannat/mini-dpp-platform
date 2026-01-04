"""
Digital Twin Registry (DTR) client for Catena-X integration.
Handles shell descriptor registration and management.
"""

import base64
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DTRConfig:
    """Configuration for DTR connection."""

    base_url: str
    auth_type: str  # "oidc" or "token"
    client_id: str | None = None
    client_secret: str | None = None
    token: str | None = None
    bpn: str | None = None


@dataclass
class ShellDescriptor:
    """AAS Shell Descriptor for DTR registration."""

    id: str
    id_short: str
    global_asset_id: str
    specific_asset_ids: list[dict[str, Any]]
    submodel_descriptors: list[dict[str, Any]]

    def to_dtr_payload(self) -> dict[str, Any]:
        """Convert to DTR API payload format."""
        return {
            "id": self.id,
            "idShort": self.id_short,
            "globalAssetId": self.global_asset_id,
            "specificAssetIds": self.specific_asset_ids,
            "submodelDescriptors": self.submodel_descriptors,
        }


class DTRClient:
    """
    Client for Catena-X Digital Twin Registry API.

    Implements shell descriptor CRUD operations following
    Tractus-X Digital Twin KIT specifications.
    """

    def __init__(self, config: DTRConfig) -> None:
        self._config = config
        self._http_client: httpx.AsyncClient | None = None
        self._access_token: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create authenticated HTTP client."""
        if self._http_client is None:
            headers = await self._get_auth_headers()
            self._http_client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._http_client

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers based on config."""
        if self._config.auth_type == "token":
            return {"Authorization": f"Bearer {self._config.token}"}

        elif self._config.auth_type == "oidc":
            # Obtain token via client credentials flow
            token = await self._obtain_oidc_token()
            return {"Authorization": f"Bearer {token}"}

        return {}

    async def _obtain_oidc_token(self) -> str:
        """Obtain OIDC token via client credentials flow."""
        settings = get_settings()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                },
            )
            response.raise_for_status()
            payload = cast(dict[str, Any], response.json())
            return str(payload.get("access_token", ""))

    async def register_shell(self, descriptor: ShellDescriptor) -> dict[str, Any]:
        """
        Register a new shell descriptor in the DTR.

        Returns the created descriptor with DTR-assigned metadata.
        """
        client = await self._get_client()

        payload = descriptor.to_dtr_payload()

        logger.info(
            "registering_shell_descriptor",
            shell_id=descriptor.id,
            submodel_count=len(descriptor.submodel_descriptors),
        )

        response = await client.post(
            "/shell-descriptors",
            json=payload,
        )
        response.raise_for_status()

        result = cast(dict[str, Any], response.json())

        logger.info(
            "shell_descriptor_registered",
            shell_id=descriptor.id,
            dtr_response_id=result.get("id"),
        )

        return result

    async def update_shell(
        self,
        shell_id: str,
        descriptor: ShellDescriptor,
    ) -> dict[str, Any]:
        """
        Update an existing shell descriptor.
        """
        client = await self._get_client()

        # Base64 encode the shell ID for path parameter
        encoded_id = base64.urlsafe_b64encode(shell_id.encode()).decode()

        response = await client.put(
            f"/shell-descriptors/{encoded_id}",
            json=descriptor.to_dtr_payload(),
        )
        response.raise_for_status()

        return cast(dict[str, Any], response.json())

    async def get_shell(self, shell_id: str) -> dict[str, Any] | None:
        """
        Retrieve a shell descriptor by ID.
        """
        client = await self._get_client()

        encoded_id = base64.urlsafe_b64encode(shell_id.encode()).decode()

        try:
            response = await client.get(f"/shell-descriptors/{encoded_id}")
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def delete_shell(self, shell_id: str) -> bool:
        """
        Delete a shell descriptor from DTR.
        """
        client = await self._get_client()

        encoded_id = base64.urlsafe_b64encode(shell_id.encode()).decode()

        response = await client.delete(f"/shell-descriptors/{encoded_id}")
        return response.status_code in (200, 204, 404)

    async def test_connection(self) -> dict[str, Any]:
        """
        Test DTR connectivity and authentication.

        Returns connection status and any error details.
        """
        try:
            client = await self._get_client()

            # Try to list shell descriptors (limited)
            response = await client.get(
                "/shell-descriptors",
                params={"limit": 1},
            )
            response.raise_for_status()

            return {
                "status": "connected",
                "dtr_url": self._config.base_url,
                "auth_type": self._config.auth_type,
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

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
