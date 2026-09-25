from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# One engine (and connection pool) per process. Creating it doesn't connect; the first query does.
engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)

# expire_on_commit=False: objects stay readable after commit instead of triggering
# a lazy reload, which would need an implicit await and fails under asyncio.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the request ends."""
    async with SessionLocal() as session:
        yield session
