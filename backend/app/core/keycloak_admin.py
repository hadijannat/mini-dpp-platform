"""
Keycloak Admin API client for user management operations.

Uses the dpp-backend service account (client_credentials grant) to manage
realm roles. Best-effort — failures are logged but do not block DB updates.
"""

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class KeycloakAdminClient:
    """Thin wrapper around the Keycloak Admin REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._server_url = settings.keycloak_server_url
        self._realm = settings.keycloak_realm
        self._client_id = settings.keycloak_client_id
        self._client_secret = settings.keycloak_client_secret
        self._base = f"{self._server_url}/admin/realms/{self._realm}"

    async def _get_service_account_token(self) -> str:
        """Obtain an access token via client_credentials grant."""
        token_url = f"{self._server_url}/realms/{self._realm}/protocol/openid-connect/token"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return str(data["access_token"])

    async def _get_role_representation(self, token: str, role_name: str) -> dict[str, Any] | None:
        """Look up a realm role by name."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base}/roles/{role_name}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result

    async def assign_realm_role(self, user_id: str, role_name: str) -> bool:
        """Assign a realm role to a Keycloak user. Returns True on success."""
        try:
            token = await self._get_service_account_token()
            role_rep = await self._get_role_representation(token, role_name)
            if not role_rep:
                logger.warning("keycloak_role_not_found", role=role_name)
                return False

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base}/users/{user_id}/role-mappings/realm",
                    headers={"Authorization": f"Bearer {token}"},
                    json=[role_rep],
                    timeout=10.0,
                )
                resp.raise_for_status()

            logger.info("keycloak_role_assigned", user_id=user_id, role=role_name)
            return True
        except Exception:
            logger.exception("keycloak_role_assign_failed", user_id=user_id, role=role_name)
            return False

    async def remove_realm_role(self, user_id: str, role_name: str) -> bool:
        """Remove a realm role from a Keycloak user. Returns True on success."""
        try:
            token = await self._get_service_account_token()
            role_rep = await self._get_role_representation(token, role_name)
            if not role_rep:
                logger.warning("keycloak_role_not_found", role=role_name)
                return False

            async with httpx.AsyncClient() as client:
                resp = await client.request(
                    "DELETE",
                    f"{self._base}/users/{user_id}/role-mappings/realm",
                    headers={"Authorization": f"Bearer {token}"},
                    json=[role_rep],
                    timeout=10.0,
                )
                resp.raise_for_status()

            logger.info("keycloak_role_removed", user_id=user_id, role=role_name)
            return True
        except Exception:
            logger.exception("keycloak_role_remove_failed", user_id=user_id, role=role_name)
            return False
