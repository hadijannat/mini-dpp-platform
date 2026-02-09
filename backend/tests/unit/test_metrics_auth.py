"""Tests for /metrics endpoint authentication gating (H-3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _clear_settings():
    """Clear cached settings before/after each test."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestMetricsAuthProduction:
    """Verify /metrics is gated in production-like config."""

    def test_metrics_returns_404_when_no_token_in_production(self, _clear_settings):
        """Production with empty metrics_auth_token should return 404."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "ENCRYPTION_MASTER_KEY": "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
                "DPP_SIGNING_KEY": "fake-signing-key-for-test",
                "CORS_ORIGINS": '["https://dpp-platform.dev"]',
                "METRICS_AUTH_TOKEN": "",
                "AUTO_PROVISION_DEFAULT_TENANT": "false",
                "OPA_ENABLED": "true",
            },
            clear=False,
        ):
            from app.main import create_application

            test_app = create_application()
            client = TestClient(test_app)
            resp = client.get("/metrics")
            assert resp.status_code == 404

    def test_metrics_returns_401_without_bearer(self, _clear_settings):
        """Production with token set but no auth header should return 401."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "ENCRYPTION_MASTER_KEY": "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
                "DPP_SIGNING_KEY": "fake-signing-key-for-test",
                "CORS_ORIGINS": '["https://dpp-platform.dev"]',
                "METRICS_AUTH_TOKEN": "super-secret-token",
                "AUTO_PROVISION_DEFAULT_TENANT": "false",
                "OPA_ENABLED": "true",
            },
            clear=False,
        ):
            from app.main import create_application

            test_app = create_application()
            client = TestClient(test_app)
            resp = client.get("/metrics")
            assert resp.status_code == 401

    def test_metrics_returns_401_with_wrong_token(self, _clear_settings):
        """Production with wrong bearer token should return 401."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "ENCRYPTION_MASTER_KEY": "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
                "DPP_SIGNING_KEY": "fake-signing-key-for-test",
                "CORS_ORIGINS": '["https://dpp-platform.dev"]',
                "METRICS_AUTH_TOKEN": "super-secret-token",
                "AUTO_PROVISION_DEFAULT_TENANT": "false",
                "OPA_ENABLED": "true",
            },
            clear=False,
        ):
            from app.main import create_application

            test_app = create_application()
            client = TestClient(test_app)
            resp = client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
            assert resp.status_code == 401

    def test_metrics_returns_200_with_correct_token(self, _clear_settings):
        """Production with correct bearer token should return metrics."""
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "production",
                "ENCRYPTION_MASTER_KEY": "dGVzdC1rZXktMzItYnl0ZXMtbG9uZy4u",
                "DPP_SIGNING_KEY": "fake-signing-key-for-test",
                "CORS_ORIGINS": '["https://dpp-platform.dev"]',
                "METRICS_AUTH_TOKEN": "super-secret-token",
                "AUTO_PROVISION_DEFAULT_TENANT": "false",
                "OPA_ENABLED": "true",
            },
            clear=False,
        ):
            from app.main import create_application

            test_app = create_application()
            client = TestClient(test_app)
            resp = client.get("/metrics", headers={"Authorization": "Bearer super-secret-token"})
            assert resp.status_code == 200
            assert "text/plain" in resp.headers.get("content-type", "")
