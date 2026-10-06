from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs import ingest as ingest_job


def test_main_runs_ingest_for_category_and_days(
    test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, datetime]] = []

    async def fake_ingest_category(
        client: httpx2.AsyncClient, session: AsyncSession, category: str, since: datetime
    ) -> int:
        # The job must hand over a session that can really reach the database.
        assert await session.scalar(text("SELECT 1")) == 1
        calls.append((category, since))
        return 7

    monkeypatch.setattr(ingest_job, "ingest_category", fake_ingest_category)

    ingest_job.main(["cs.LG", "--days", "30"])

    ((category, since),) = calls
    assert category == "cs.LG"
    expected = datetime.now(UTC) - timedelta(days=30)
    assert abs(since - expected) < timedelta(minutes=1)


def test_ingest_returns_new_paper_count(
    test_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_ingest_category(*args: object) -> int:
        return 7

    monkeypatch.setattr(ingest_job, "ingest_category", fake_ingest_category)

    assert ingest_job.ingest("cs.LG", datetime(2024, 1, 1, tzinfo=UTC)) == 7
