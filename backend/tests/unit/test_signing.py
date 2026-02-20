"""
Unit tests for DPP JWS signing and production config validation.
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.dpps.service import DPPService, SigningError


@pytest.fixture
def service() -> DPPService:
    """Create a DPPService with a mock session."""
    return DPPService(AsyncMock())


def test_sign_digest_returns_none_when_no_key(service: DPPService) -> None:
    """When no signing key is configured, _sign_digest returns None."""
    with patch.object(service, "_settings") as mock_settings:
        mock_settings.dpp_signing_key = ""
        result = service._sign_digest("abc123")
    assert result is None


def test_sign_digest_raises_on_invalid_key(service: DPPService) -> None:
    """When signing key is present but invalid, SigningError is raised."""
    with patch.object(service, "_settings") as mock_settings:
        mock_settings.dpp_signing_key = "not-a-valid-pem-key"
        mock_settings.dpp_signing_algorithm = "RS256"
        mock_settings.dpp_signing_key_id = "test-kid"
        with pytest.raises(SigningError, match="JWS signing failed"):
            service._sign_digest("abc123")


def test_production_config_rejects_empty_signing_key() -> None:
    """Settings with env=production and empty signing key raises ValueError."""
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValueError, match="dpp_signing_key must be set"):
        Settings(
            environment="production",
            encryption_master_key="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
            cors_origins=["https://dpp-platform.dev"],
            opa_enabled=True,
            dpp_signing_key="",
            audit_signing_key="fake-audit-signing-key",
        )


def test_dev_config_warns_on_empty_signing_key() -> None:
    """Settings with env=development and empty signing key emits a warning."""
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        Settings(
            environment="development",
            dpp_signing_key="",
        )
    signing_warnings = [x for x in w if "dpp_signing_key" in str(x.message)]
    assert len(signing_warnings) >= 1


def test_production_config_rejects_auto_provision_default_tenant() -> None:
    """Settings with env=production and auto_provision_default_tenant=True raises ValueError."""
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValueError, match="auto_provision_default_tenant must be False"):
        Settings(
            environment="production",
            encryption_master_key="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
            cors_origins=["https://dpp-platform.dev"],
            dpp_signing_key="fake-key",
            audit_signing_key="another-fake-key",
            opa_enabled=True,
            auto_provision_default_tenant=True,
        )
