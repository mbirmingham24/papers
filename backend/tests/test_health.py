from collections.abc import AsyncIterator

from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_session
from app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health_ok_when_database_reachable(test_database: str) -> None:
    async with _client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_503_when_database_unreachable() -> None:
    # Port 1 on localhost: nothing listens there, so the connection is refused immediately.
    dead_engine = create_async_engine("postgresql+asyncpg://x:x@127.0.0.1:1/x")

    async def dead_session() -> AsyncIterator[AsyncSession]:
        async with async_sessionmaker(dead_engine)() as session:
            yield session

    app.dependency_overrides[get_session] = dead_session
    try:
        async with _client() as client:
            response = await client.get("/health")
    finally:
        app.dependency_overrides.clear()
        await dead_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unreachable"}
