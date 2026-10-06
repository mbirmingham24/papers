import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Tests get their own database, taken from TEST_DATABASE_URL and never from DATABASE_URL:
# migration tests drop every table, so they must not be able to reach the dev DB.
# This runs before any test module imports the app, so settings pick it up.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://papers:papers@localhost:5432/papers_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Redis DB 15, not 0: once the app caches embeddings in DB 0, tests can flush theirs
# without wiping the dev cache.
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["ENVIRONMENT"] = "test"


async def _create_database_if_missing(url: str) -> None:
    target = make_url(url)
    # CREATE DATABASE can't run inside a transaction, hence AUTOCOMMIT,
    # and can't target the database it's connected to, hence the "postgres" maintenance DB.
    engine = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    await engine.dispose()


@pytest.fixture(scope="session")
def test_database() -> str:
    asyncio.run(_create_database_if_missing(TEST_DATABASE_URL))
    return TEST_DATABASE_URL


@pytest.fixture
def alembic_config(test_database: str) -> Config:
    return Config(Path(__file__).parents[1] / "alembic.ini")


@pytest.fixture
def migrated_database(alembic_config: Config) -> None:
    # Sync on purpose: Alembic's env.py calls asyncio.run(), which can't nest inside
    # the running loop an async fixture would give it.
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def db_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    """A session on the migrated test DB, starting from an empty papers table."""
    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        await session.execute(text("TRUNCATE papers RESTART IDENTITY"))
        await session.commit()
        yield session
