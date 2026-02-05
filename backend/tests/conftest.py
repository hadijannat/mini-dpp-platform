"""
Pytest fixtures for backend testing.
Provides database sessions, test clients, and mock data factories.
"""

import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security.oidc import TokenPayload, optional_verify_token, verify_token
from app.db.models import Base, Tenant, TenantMember, TenantRole, TenantStatus
from app.db.session import get_db_session
from app.main import create_application

# Test database URL
TEST_DATABASE_URL = (
    os.getenv("TEST_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or "postgresql+asyncpg://test:test@localhost:5433/dpp_test"
)


@pytest.fixture(autouse=True)
def ensure_test_allowed_issuers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test env accepts both localhost Keycloak issuers."""
    allowed = os.getenv("KEYCLOAK_ALLOWED_ISSUERS", "")
    issuers = [item.strip() for item in allowed.split(",") if item.strip()]
    for issuer in (
        "http://localhost:8080/realms/dpp-platform",
        "http://localhost:8081/realms/dpp-platform",
    ):
        if issuer not in issuers:
            issuers.append(issuer)
    monkeypatch.setenv("KEYCLOAK_ALLOWED_ISSUERS", ",".join(issuers))
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        await conn.execute(
            text("""
CREATE OR REPLACE FUNCTION uuid_generate_v7()
RETURNS uuid AS $$
DECLARE
    unix_ts_ms bytea;
    uuid_bytes bytea;
BEGIN
    unix_ts_ms = substring(int8send(floor(extract(epoch from clock_timestamp()) * 1000)::bigint) from 3);
    uuid_bytes = unix_ts_ms || gen_random_bytes(10);

    -- Set version 7
    uuid_bytes = set_byte(uuid_bytes, 6, (get_byte(uuid_bytes, 6) & 15) | 112);
    -- Set variant (RFC 4122)
    uuid_bytes = set_byte(uuid_bytes, 8, (get_byte(uuid_bytes, 8) & 63) | 128);

    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql VOLATILE;
        """)
        )
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session for each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing."""
    os.environ.setdefault("OPA_ENABLED", "false")
    get_settings.cache_clear()
    app = create_application()

    def _mock_payload() -> TokenPayload:
        return TokenPayload(
            sub="test-user-123",
            email="test@example.com",
            preferred_username="testuser",
            roles=["publisher"],
            bpn="BPNL00000001TEST",
            org="Test Organization",
            clearance="public",
            exp=datetime.now(UTC),
            iat=datetime.now(UTC),
            raw_claims={},
        )

    async def override_verify_token(request: Request) -> TokenPayload:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return _mock_payload()

    async def override_optional_verify_token(
        credentials: HTTPAuthorizationCredentials | None = None,
    ) -> TokenPayload | None:
        if credentials is None:
            return None
        return _mock_payload()

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        tenant = Tenant(slug="default", name="Default Tenant", status=TenantStatus.ACTIVE)
        session.add(tenant)
        await session.flush()

        session.add(
            TenantMember(
                tenant_id=tenant.id,
                user_subject="test-user-123",
                role=TenantRole.PUBLISHER,
            )
        )
        session.add(
            TenantMember(
                tenant_id=tenant.id,
                user_subject="viewer-user-456",
                role=TenantRole.VIEWER,
            )
        )
        await session.commit()

    async def override_get_db_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[verify_token] = override_verify_token
    app.dependency_overrides[optional_verify_token] = override_optional_verify_token
    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_user_token() -> dict[str, Any]:
    """Generate a mock JWT token payload for testing."""
    return {
        "sub": "test-user-123",
        "email": "test@example.com",
        "preferred_username": "testuser",
        "realm_access": {"roles": ["publisher"]},
        "bpn": "BPNL00000001TEST",
        "org": "Test Organization",
        "clearance": "public",
    }


@pytest.fixture
def mock_viewer_token() -> dict[str, Any]:
    """Generate a mock viewer JWT token payload."""
    return {
        "sub": "viewer-user-456",
        "email": "viewer@example.com",
        "preferred_username": "viewer",
        "realm_access": {"roles": ["viewer"]},
        "clearance": "public",
    }


@pytest.fixture
def mock_auth_headers() -> dict[str, str]:
    """Mock Authorization header."""
    return {"Authorization": "Bearer test-token"}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run e2e tests that require the full docker-compose stack.",
    )
    parser.addoption(
        "--run-goldens",
        action="store_true",
        default=False,
        help="Run golden snapshot tests against refreshed IDTA templates.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_e2e = bool(config.getoption("--run-e2e") or os.getenv("RUN_E2E") == "1")
    run_goldens = bool(config.getoption("--run-goldens") or os.getenv("RUN_GOLDENS") == "1")

    if not run_e2e:
        skip_e2e = pytest.mark.skip(reason="e2e tests require --run-e2e or RUN_E2E=1")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)

    if not run_goldens:
        skip_goldens = pytest.mark.skip(
            reason="golden tests require --run-goldens or RUN_GOLDENS=1"
        )
        for item in items:
            if "golden" in item.keywords:
                item.add_marker(skip_goldens)
