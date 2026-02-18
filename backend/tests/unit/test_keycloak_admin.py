"""Unit tests for the KeycloakAdminClient."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.keycloak_admin import KeycloakAdminClient


def _response(status_code: int, json: dict | None = None) -> httpx.Response:
    """Create an httpx.Response with a dummy request (needed for raise_for_status)."""
    request = httpx.Request("GET", "http://test")
    if json is not None:
        return httpx.Response(status_code, json=json, request=request)
    return httpx.Response(status_code, request=request)


@pytest.fixture
def kc_client() -> KeycloakAdminClient:
    with patch("app.core.keycloak_admin.get_settings") as mock:
        settings = MagicMock()
        settings.keycloak_server_url = "http://localhost:8080"
        settings.keycloak_realm = "dpp-platform"
        settings.keycloak_client_id = "dpp-backend"
        settings.keycloak_client_secret = "secret"
        mock.return_value = settings
        return KeycloakAdminClient()


@pytest.mark.asyncio
async def test_assign_realm_role_success(kc_client: KeycloakAdminClient) -> None:
    """Successful role assignment returns True."""
    token_resp = _response(200, {"access_token": "test-token", "token_type": "Bearer"})
    role_resp = _response(200, {"id": "role-id-1", "name": "publisher"})
    assign_resp = _response(204)

    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_client.post = AsyncMock(side_effect=[token_resp, assign_resp])
        mock_client.get = AsyncMock(return_value=role_resp)

        mock_client_cls.return_value = mock_client

        result = await kc_client.assign_realm_role("user-id-1", "publisher")

    assert result is True


@pytest.mark.asyncio
async def test_assign_realm_role_not_found(kc_client: KeycloakAdminClient) -> None:
    """Returns False when the role doesn't exist in Keycloak."""
    token_resp = _response(200, {"access_token": "test-token", "token_type": "Bearer"})
    role_not_found = _response(404)

    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.get = AsyncMock(return_value=role_not_found)

        mock_client_cls.return_value = mock_client

        result = await kc_client.assign_realm_role("user-id-1", "nonexistent")

    assert result is False


@pytest.mark.asyncio
async def test_assign_realm_role_network_error(kc_client: KeycloakAdminClient) -> None:
    """Returns False on network failure (best-effort)."""
    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        mock_client_cls.return_value = mock_client

        result = await kc_client.assign_realm_role("user-id-1", "publisher")

    assert result is False


@pytest.mark.asyncio
async def test_remove_realm_role_success(kc_client: KeycloakAdminClient) -> None:
    """Successful role removal returns True."""
    token_resp = _response(200, {"access_token": "test-token", "token_type": "Bearer"})
    role_resp = _response(200, {"id": "role-id-1", "name": "publisher"})
    remove_resp = _response(204)

    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.get = AsyncMock(return_value=role_resp)
        mock_client.request = AsyncMock(return_value=remove_resp)

        mock_client_cls.return_value = mock_client

        result = await kc_client.remove_realm_role("user-id-1", "publisher")

    assert result is True


@pytest.mark.asyncio
async def test_send_verify_email_success(kc_client: KeycloakAdminClient) -> None:
    """Successful verify-email enqueue returns True."""
    token_resp = _response(200, {"access_token": "test-token", "token_type": "Bearer"})
    enqueue_resp = _response(204)

    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.put = AsyncMock(return_value=enqueue_resp)
        mock_client_cls.return_value = mock_client

        result = await kc_client.send_verify_email(
            "user-id-1",
            redirect_uri="https://dpp-platform.dev/welcome",
            client_id="dpp-frontend",
        )

    assert result is True
    mock_client.put.assert_awaited_once_with(
        "http://localhost:8080/admin/realms/dpp-platform/users/user-id-1/execute-actions-email",
        headers={"Authorization": "Bearer test-token"},
        params={
            "redirect_uri": "https://dpp-platform.dev/welcome",
            "client_id": "dpp-frontend",
        },
        json=["VERIFY_EMAIL"],
        timeout=10.0,
    )


@pytest.mark.asyncio
async def test_send_verify_email_failure(kc_client: KeycloakAdminClient) -> None:
    """Returns False when verify-email enqueue fails."""
    token_resp = _response(200, {"access_token": "test-token", "token_type": "Bearer"})
    enqueue_resp = _response(500)

    with patch("app.core.keycloak_admin.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.put = AsyncMock(return_value=enqueue_resp)
        mock_client_cls.return_value = mock_client

        result = await kc_client.send_verify_email("user-id-1")

    assert result is False
