"""
Unit tests for security headers middleware.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.middleware import SecurityHeadersMiddleware


@pytest.mark.asyncio
async def test_response_includes_csp_header() -> None:
    """Middleware should add Content-Security-Policy header."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    request = MagicMock()
    response = MagicMock()
    response.headers = {}

    async def call_next(_request):  # type: ignore[no-untyped-def]
        return response

    result = await middleware.dispatch(request, call_next)
    assert "Content-Security-Policy" in result.headers


@pytest.mark.asyncio
async def test_csp_allows_self_scripts() -> None:
    """CSP should allow scripts from same origin."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    request = MagicMock()
    response = MagicMock()
    response.headers = {}

    async def call_next(_request):  # type: ignore[no-untyped-def]
        return response

    result = await middleware.dispatch(request, call_next)
    csp = result.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_csp_allows_keycloak_connect() -> None:
    """CSP connect-src should include Keycloak auth domain."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    request = MagicMock()
    response = MagicMock()
    response.headers = {}

    async def call_next(_request):  # type: ignore[no-untyped-def]
        return response

    result = await middleware.dispatch(request, call_next)
    csp = result.headers["Content-Security-Policy"]
    assert "https://auth.dpp-platform.dev" in csp


@pytest.mark.asyncio
async def test_existing_security_headers_still_present() -> None:
    """Existing security headers should still be set."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    request = MagicMock()
    response = MagicMock()
    response.headers = {}

    async def call_next(_request):  # type: ignore[no-untyped-def]
        return response

    result = await middleware.dispatch(request, call_next)
    assert result.headers["X-Content-Type-Options"] == "nosniff"
    assert result.headers["X-Frame-Options"] == "DENY"
