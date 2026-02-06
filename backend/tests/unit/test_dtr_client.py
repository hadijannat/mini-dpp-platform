"""
Unit tests for the DTR (Digital Twin Registry) client.
"""

import base64
from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.connectors.catenax.dtr_client import DTRClient, DTRConfig, ShellDescriptor


@pytest.fixture
def token_config() -> DTRConfig:
    """DTR config using static token authentication."""
    return DTRConfig(
        base_url="https://dtr.example.com",
        auth_type="token",
        token="test-bearer-token",
        bpn="BPNL000000000001",
    )


@pytest.fixture
def oidc_config() -> DTRConfig:
    """DTR config using OIDC client-credentials authentication."""
    return DTRConfig(
        base_url="https://dtr.example.com",
        auth_type="oidc",
        client_id="my-client",
        client_secret="my-secret",
        bpn="BPNL000000000001",
    )


@pytest.fixture
def client(token_config: DTRConfig) -> DTRClient:
    return DTRClient(token_config)


@pytest.fixture
def sample_descriptor() -> ShellDescriptor:
    return ShellDescriptor(
        id="urn:uuid:abc-123",
        id_short="DPP_Test",
        global_asset_id="urn:asset:global-1",
        specific_asset_ids=[{"name": "manufacturerPartId", "value": "MP-001"}],
        submodel_descriptors=[{"id": "urn:sm:1", "idShort": "Nameplate"}],
    )


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> httpx.Response:
    """Create a real httpx.Response for mocking."""
    request = httpx.Request("GET", "https://dtr.example.com/test")
    response = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=request,
    )
    return response


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_validate_config_strips_trailing_slash(self):
        """Trailing slash on base_url is stripped during validation."""
        config = DTRConfig(
            base_url="https://dtr.example.com/",
            auth_type="token",
            token="tok",
        )
        client = DTRClient(config)
        client._validate_config()
        assert client._config.base_url == "https://dtr.example.com"

    def test_validate_config_empty_url_raises(self):
        """Empty or whitespace-only base_url raises ValueError."""
        config = DTRConfig(base_url="   ", auth_type="token", token="tok")
        client = DTRClient(config)
        with pytest.raises(ValueError, match="base URL is required"):
            client._validate_config()

    def test_validate_config_invalid_auth_type_raises(self):
        """Unsupported auth_type raises ValueError."""
        config = DTRConfig(
            base_url="https://dtr.example.com",
            auth_type="basic",
            token="tok",
        )
        client = DTRClient(config)
        with pytest.raises(ValueError, match="must be 'oidc' or 'token'"):
            client._validate_config()

    def test_validate_config_token_auth_requires_token(self):
        """Token auth with an empty token raises ValueError."""
        config = DTRConfig(
            base_url="https://dtr.example.com",
            auth_type="token",
            token="",
        )
        client = DTRClient(config)
        with pytest.raises(ValueError, match="token is required"):
            client._validate_config()

    def test_validate_config_oidc_requires_credentials(self):
        """OIDC auth without client_id or client_secret raises ValueError."""
        config = DTRConfig(
            base_url="https://dtr.example.com",
            auth_type="oidc",
            client_id=None,
            client_secret=None,
        )
        client = DTRClient(config)
        with pytest.raises(ValueError, match="client_id and client_secret"):
            client._validate_config()


# ---------------------------------------------------------------------------
# HTTP operations
# ---------------------------------------------------------------------------


class TestShellOperations:
    @pytest.mark.asyncio
    async def test_register_shell_posts_payload(
        self, client: DTRClient, sample_descriptor: ShellDescriptor
    ):
        """register_shell sends POST /shell-descriptors with descriptor JSON."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post.return_value = _mock_response(201, {"id": sample_descriptor.id})
        client._http_client = mock_http

        result = await client.register_shell(sample_descriptor)

        mock_http.post.assert_awaited_once_with(
            "/shell-descriptors",
            json=sample_descriptor.to_dtr_payload(),
        )
        assert result["id"] == sample_descriptor.id

    @pytest.mark.asyncio
    async def test_get_shell_returns_none_on_404(self, client: DTRClient):
        """get_shell returns None when the DTR responds 404."""
        resp_404 = _mock_response(404, {"error": "not found"})
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = resp_404

        client._http_client = mock_http

        result = await client.get_shell("urn:uuid:missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_shell_reraises_non_404(self, client: DTRClient):
        """get_shell re-raises HTTPStatusError for non-404 responses."""
        resp_500 = _mock_response(500, {"error": "server error"})
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = resp_500

        client._http_client = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            await client.get_shell("urn:uuid:broken")

    @pytest.mark.asyncio
    async def test_update_shell_encodes_id_base64url(
        self, client: DTRClient, sample_descriptor: ShellDescriptor
    ):
        """update_shell base64url-encodes the shell ID in the URL path."""
        shell_id = "urn:uuid:abc-123"
        expected_encoded = base64.urlsafe_b64encode(shell_id.encode()).decode()

        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.put.return_value = _mock_response(200, {"id": shell_id})
        client._http_client = mock_http

        await client.update_shell(shell_id, sample_descriptor)

        call_args = mock_http.put.call_args
        assert expected_encoded in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_shell_returns_true_on_204(self, client: DTRClient):
        """delete_shell returns True on HTTP 204 No Content."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.delete.return_value = _mock_response(204)
        client._http_client = mock_http

        assert await client.delete_shell("urn:uuid:del-1") is True

    @pytest.mark.asyncio
    async def test_delete_shell_returns_true_on_404(self, client: DTRClient):
        """delete_shell returns True on 404 (idempotent delete)."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.delete.return_value = _mock_response(404)
        client._http_client = mock_http

        assert await client.delete_shell("urn:uuid:already-gone") is True

    @pytest.mark.asyncio
    async def test_test_connection_returns_error_on_http_failure(self, client: DTRClient):
        """test_connection returns structured error dict on HTTPStatusError."""
        resp_401 = _mock_response(401, {"error": "unauthorized"})
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.get.return_value = resp_401
        client._http_client = mock_http

        result = await client.test_connection()

        assert result["status"] == "error"
        assert result["error_code"] == 401

    @pytest.mark.asyncio
    async def test_close_clears_client(self, client: DTRClient):
        """After close(), internal _http_client is set to None."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        client._http_client = mock_http

        await client.close()

        assert client._http_client is None
        mock_http.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_token_auth_sets_bearer_header(self, token_config: DTRConfig):
        """Token auth populates the Authorization: Bearer header on the client."""
        dtr = DTRClient(token_config)
        client = await dtr._get_client()
        assert client.headers["Authorization"] == f"Bearer {token_config.token}"
