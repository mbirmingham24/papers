import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs import ingest as ingest_job
from app.jobs.queue import INGEST_TIMEOUT_S, enqueue_ingest


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


@pytest.fixture
def queue() -> Iterator[Queue]:
    """A queue in the test Redis DB, emptied afterwards. Nothing is listening on it."""
    queue = Queue("test", connection=Redis.from_url(os.environ["REDIS_URL"]))
    yield queue
    queue.delete(delete_jobs=True)


def test_enqueue_ingest_queues_a_job_the_worker_can_run(queue: Queue) -> None:
    since = datetime(2024, 1, 1, tzinfo=UTC)

    job = enqueue_ingest("cs.LG", since, queue=queue)

    assert queue.job_ids == [job.id]
    fetched = queue.fetch_job(job.id)
    assert fetched is not None
    # .func imports the dotted path the way the worker will, so a typo in it fails here.
    assert fetched.func is ingest_job.ingest
    assert fetched.args == ("cs.LG", since)
    assert fetched.timeout == INGEST_TIMEOUT_S
    assert fetched.retries_left == 3


def test_main_with_enqueue_queues_instead_of_running(monkeypatch: pytest.MonkeyPatch) -> None:
    queued: list[str] = []

    class FakeJob:
        id = "abc"

    def fake_enqueue(category: str, since: datetime) -> FakeJob:
        queued.append(category)
        return FakeJob()

    def fail(*args: object) -> int:
        raise AssertionError("ingest ran inline")

    monkeypatch.setattr(ingest_job, "enqueue_ingest", fake_enqueue)
    monkeypatch.setattr(ingest_job, "ingest", fail)

    ingest_job.main(["cs.LG", "--enqueue"])

    assert queued == ["cs.LG"]
