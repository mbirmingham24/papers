import asyncio
import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

# Tests get their own database, taken from TEST_DATABASE_URL and never from DATABASE_URL:
# migration tests drop every table, so they must not be able to reach the dev DB.
# This runs before any test module imports the app, so settings pick it up.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://papers:papers@localhost:5432/papers_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
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
