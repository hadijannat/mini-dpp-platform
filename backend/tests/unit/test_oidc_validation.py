"""
Unit tests for OIDC/JWT token validation, including azp claim validation.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from jwt.exceptions import InvalidIssuerError

from app.core.config import get_settings
from app.core.security.oidc import _decode_token


@pytest.fixture
def mock_signing_key():
    """Mock JWKS signing key for tests."""
    return {
        "kty": "RSA",
        "kid": "test-key-id",
        "use": "sig",
        "n": "mock-n-value",
        "e": "AQAB",
    }


@pytest.fixture
def valid_payload():
    """Base valid token payload."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "preferred_username": "testuser",
        "exp": int((datetime.now(UTC).timestamp()) + 3600),
        "iat": int(datetime.now(UTC).timestamp()),
        "iss": "http://localhost:8080/realms/dpp-platform",
        "azp": "dpp-backend",  # Authorized party matching our client
        "realm_access": {"roles": ["publisher"]},
    }


@pytest.mark.asyncio
async def test_token_with_correct_azp_accepted(mock_signing_key, valid_payload, monkeypatch):
    """Token with azp matching keycloak_client_id should be accepted."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        result = await _decode_token("valid.jwt.token")

    assert result.sub == "test-user-123"
    assert result.email == "test@example.com"


@pytest.mark.asyncio
async def test_token_with_allowed_azp_accepted(mock_signing_key, valid_payload, monkeypatch):
    """Token with azp in allowed list should be accepted."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    monkeypatch.setenv("KEYCLOAK_ALLOWED_CLIENT_IDS", "dpp-frontend")
    get_settings.cache_clear()

    valid_payload["azp"] = "dpp-frontend"

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        result = await _decode_token("allowed.azp.token")

        assert result.sub == "test-user-123"


@pytest.mark.asyncio
async def test_token_with_wrong_azp_rejected(mock_signing_key, valid_payload, monkeypatch):
    """Token with azp not matching keycloak_client_id should be rejected."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    # Set azp to a different client
    valid_payload["azp"] = "other-client-app"

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        with pytest.raises(HTTPException) as exc:
            await _decode_token("wrong.azp.token")

        assert exc.value.status_code == 401
        assert "Token not authorized for this client" in exc.value.detail


@pytest.mark.asyncio
async def test_token_without_azp_accepted(mock_signing_key, valid_payload, monkeypatch):
    """Token without azp claim should be accepted for backward compatibility."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    # Remove azp from payload
    del valid_payload["azp"]
    valid_payload["aud"] = "dpp-backend"

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        result = await _decode_token("no.azp.token")

        # Should succeed without azp
        assert result.sub == "test-user-123"


@pytest.mark.asyncio
async def test_token_without_azp_or_aud_rejected(mock_signing_key, valid_payload, monkeypatch):
    """Token without azp or aud should be rejected when client IDs are enforced."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    del valid_payload["azp"]
    valid_payload.pop("aud", None)

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        with pytest.raises(HTTPException) as exc:
            await _decode_token("no.azp.or.aud.token")

        assert exc.value.status_code == 401
        assert "Token not authorized for this client" in exc.value.detail


@pytest.mark.asyncio
async def test_token_with_invalid_issuer_rejected(mock_signing_key, valid_payload, monkeypatch):
    """Token with invalid issuer should be rejected."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    # Set invalid issuer
    valid_payload["iss"] = "https://malicious-idp.com/realms/fake"

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        with pytest.raises(HTTPException) as exc:
            await _decode_token("bad.issuer.token")

        assert exc.value.status_code == 401
        assert "Invalid token issuer" in exc.value.detail


@pytest.mark.asyncio
async def test_jwt_decode_called_with_verify_iss_true(mock_signing_key, valid_payload, monkeypatch):
    """jwt.decode should be called with verify_iss=True and issuer list."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.return_value = valid_payload

        await _decode_token("valid.jwt.token")

        call_kwargs = mock_decode.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        assert options["verify_iss"] is True
        issuer_arg = call_kwargs.kwargs.get("issuer") or call_kwargs[1].get("issuer")
        assert isinstance(issuer_arg, list)
        assert "http://localhost:8080/realms/dpp-platform" in issuer_arg


@pytest.mark.asyncio
async def test_pyjwt_invalid_issuer_error_handled(mock_signing_key, monkeypatch):
    """PyJWT InvalidIssuerError should be caught and return 401."""
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "dpp-backend")
    get_settings.cache_clear()

    with (
        patch("app.core.security.oidc._jwks_client") as mock_jwks,
        patch("app.core.security.oidc.jwt.decode") as mock_decode,
        patch("app.core.security.oidc.jwt.get_unverified_header") as mock_header,
    ):
        mock_header.return_value = {"kid": "test-key-id"}
        mock_jwks.get_signing_key = AsyncMock(return_value=mock_signing_key)
        mock_decode.side_effect = InvalidIssuerError("Invalid issuer")

        with pytest.raises(HTTPException) as exc:
            await _decode_token("bad.issuer.token")

        assert exc.value.status_code == 401
        assert "Invalid token issuer" in exc.value.detail
