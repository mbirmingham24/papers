import logging
from collections.abc import AsyncIterator, Iterator

import pytest
from httpx2 import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_session
from app.core.redis import get_redis
from app.main import app

# Port 1 on localhost: nothing listens there, so connections are refused immediately.
DEAD_HOST = "127.0.0.1:1"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def dead_database() -> AsyncIterator[None]:
    """Point the app's DB session at a database that refuses connections."""
    dead_engine = create_async_engine(f"postgresql+asyncpg://x:x@{DEAD_HOST}/x")

    async def dead_session() -> AsyncIterator[AsyncSession]:
        async with async_sessionmaker(dead_engine)() as session:
            yield session

    app.dependency_overrides[get_session] = dead_session
    yield
    await dead_engine.dispose()


@pytest.fixture
async def dead_redis() -> AsyncIterator[None]:
    """Point the app's Redis client at a server that refuses connections."""
    dead_client = Redis.from_url(f"redis://{DEAD_HOST}/0")
    app.dependency_overrides[get_redis] = lambda: dead_client
    yield
    await dead_client.aclose()


async def test_health_ok_when_dependencies_reachable(test_database: str) -> None:
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


async def test_health_503_when_database_unreachable(
    dead_database: None, caplog: pytest.LogCaptureFixture
) -> None:
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 503
    # Each check reports on its own: Redis is still up.
    assert response.json() == {"status": "error", "database": "unreachable", "redis": "ok"}
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "database check failed" in warnings[0]


async def test_health_503_when_redis_unreachable(
    test_database: str, dead_redis: None, caplog: pytest.LogCaptureFixture
) -> None:
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "ok", "redis": "unreachable"}
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "redis check failed" in warnings[0]


async def test_livez_ok_even_when_dependencies_unreachable(
    dead_database: None, dead_redis: None
) -> None:
    async with _client() as client:
        response = await client.get("/livez")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
