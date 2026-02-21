"""Tests for the GS1 Digital Link resolver public endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.modules.resolver.public_router import router
from app.modules.resolver.schemas import LinkType


def _make_link(
    *,
    identifier: str = "01/09520123456788/21/SER001",
    link_type: str = LinkType.HAS_DPP.value,
    href: str = "https://example.com/api/v1/public/default/dpps/123",
    media_type: str = "application/json",
    title: str = "Test DPP",
    hreflang: str = "en",
    priority: int = 100,
    active: bool = True,
) -> MagicMock:
    """Create a mock ResolverLink."""
    link = MagicMock()
    link.id = uuid4()
    link.tenant_id = uuid4()
    link.identifier = identifier
    link.link_type = link_type
    link.href = href
    link.media_type = media_type
    link.title = title
    link.hreflang = hreflang
    link.priority = priority
    link.dpp_id = uuid4()
    link.active = active
    link.created_by_subject = "test-user"
    link.created_at = datetime.now()
    link.updated_at = datetime.now()
    return link


@pytest.fixture()
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(mock_db: AsyncMock) -> FastAPI:
    """Create test FastAPI app with public resolver routes."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/resolve")
    test_app.include_router(router, prefix="", include_in_schema=False)

    async def _override_db() -> Any:
        yield mock_db

    test_app.dependency_overrides[get_db_session] = _override_db
    return test_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestResolverDescription:
    """Tests for /.well-known/gs1resolver endpoint."""

    @patch("app.modules.resolver.public_router.get_settings")
    def test_description_document(self, mock_settings: MagicMock, client: TestClient) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        response = client.get("/resolve/.well-known/gs1resolver")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Mini DPP Platform GS1 Digital Link Resolver"
        assert data["resolverRoot"] == "http://testserver"
        assert len(data["supportedLinkTypes"]) == len(LinkType)


class TestResolutionEndpoints:
    """Tests for GTIN resolution endpoints."""

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_gtin_only_redirect(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link(identifier="01/09520123456788")
        mock_resolve.return_value = [link]

        response = client.get("/resolve/01/09520123456788", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == link.href

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_gtin_serial_redirect(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link()
        mock_resolve.return_value = [link]

        response = client.get("/resolve/01/09520123456788/21/SER001", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == link.href
        mock_resolve.assert_called_once_with(
            "01/09520123456788/21/SER001",
            link_type_filter=None,
            tenant_id=None,
        )

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_gtin_lot_redirect(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link(identifier="01/09520123456788/10/BATCH001")
        mock_resolve.return_value = [link]

        response = client.get("/resolve/01/09520123456788/10/BATCH001", follow_redirects=False)
        assert response.status_code == 307

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_gtin_serial_lot_redirect(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link(identifier="01/09520123456788/21/SER001/10/BATCH001")
        mock_resolve.return_value = [link]

        response = client.get(
            "/resolve/01/09520123456788/21/SER001/10/BATCH001",
            follow_redirects=False,
        )
        assert response.status_code == 307

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_linkset_response(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link()
        mock_resolve.return_value = [link]

        response = client.get(
            "/resolve/01/09520123456788/21/SER001",
            headers={"Accept": "application/linkset+json"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/linkset+json"
        data = response.json()
        assert "linkset" in data
        assert len(data["linkset"]) == 1
        assert "anchor" in data["linkset"][0]

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_not_found(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = ""
        mock_settings.return_value = settings

        mock_resolve.return_value = []

        response = client.get("/resolve/01/00000000000000/21/UNKNOWN")
        assert response.status_code == 404

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_link_type_filter(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        link = _make_link(link_type=LinkType.CERTIFICATION_INFO.value)
        mock_resolve.return_value = [link]

        response = client.get(
            "/resolve/01/09520123456788/21/SER001",
            params={"linkType": LinkType.CERTIFICATION_INFO.value},
            follow_redirects=False,
        )
        assert response.status_code == 307
        mock_resolve.assert_called_once_with(
            "01/09520123456788/21/SER001",
            link_type_filter=LinkType.CERTIFICATION_INFO.value,
            tenant_id=None,
        )

    @patch("app.modules.resolver.public_router.get_settings")
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_redirect_prefers_dpp_link(
        self,
        mock_resolve: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        """When multiple link types exist, redirect prefers gs1:hasDigitalProductPassport."""
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        mock_settings.return_value = settings

        cert_link = _make_link(
            link_type=LinkType.CERTIFICATION_INFO.value,
            href="https://cert.example.com",
            priority=50,
        )
        dpp_link = _make_link(
            link_type=LinkType.HAS_DPP.value,
            href="https://dpp.example.com",
            priority=100,
        )
        # Return cert first in list — resolver should still prefer DPP
        mock_resolve.return_value = [dpp_link, cert_link]

        response = client.get("/resolve/01/09520123456788/21/SER001", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "https://dpp.example.com"

    @patch("app.modules.resolver.public_router.get_settings")
    @patch(
        "app.modules.tenant_domains.service.TenantDomainService.resolve_active_tenant_by_hostname",
        new_callable=AsyncMock,
    )
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_root_route_requires_active_domain(
        self,
        mock_resolve: AsyncMock,
        mock_resolve_domain: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        settings.api_v1_prefix = "/api/v1"
        settings.trusted_proxy_cidrs = []
        mock_settings.return_value = settings

        mock_resolve_domain.return_value = None
        response = client.get("/01/09520123456788/21/SER001", follow_redirects=False)
        assert response.status_code == 404
        mock_resolve.assert_not_called()

    @patch("app.modules.resolver.public_router.get_settings")
    @patch(
        "app.modules.tenant_domains.service.TenantDomainService.resolve_active_tenant_by_hostname",
        new_callable=AsyncMock,
    )
    @patch("app.modules.resolver.service.ResolverService.resolve", new_callable=AsyncMock)
    def test_root_route_scopes_to_tenant(
        self,
        mock_resolve: AsyncMock,
        mock_resolve_domain: AsyncMock,
        mock_settings: MagicMock,
        client: TestClient,
    ) -> None:
        settings = MagicMock()
        settings.resolver_base_url = "https://resolver.example.com"
        settings.api_v1_prefix = "/api/v1"
        settings.trusted_proxy_cidrs = []
        settings.db_admin_role = None
        mock_settings.return_value = settings

        tenant_id = uuid4()
        mock_resolve_domain.return_value = tenant_id
        mock_resolve.return_value = [_make_link()]

        response = client.get(
            "/01/09520123456788/21/SER001",
            headers={"host": "acme.example.com"},
            follow_redirects=False,
        )
        assert response.status_code == 307
        mock_resolve.assert_called_once_with(
            "01/09520123456788/21/SER001",
            link_type_filter=None,
            tenant_id=tenant_id,
        )
