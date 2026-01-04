"""
Pytest fixtures for backend testing.
Provides database sessions, test clients, and mock data factories.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import Settings
from app.db.models import Base
from app.main import create_application

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5433/dpp_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

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
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing."""
    app = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
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
