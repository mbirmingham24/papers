"""The RQ queue: jobs are put here (in Redis) and a separate worker process runs them."""

from datetime import datetime

from redis import Redis
from rq import Queue, Retry
from rq.job import Job

from app.core.config import get_settings

QUEUE_NAME = "default"

# RQ kills a job after 3 minutes by default; a backfill with rate-limit waits runs far longer.
INGEST_TIMEOUT_S = 30 * 60
# If a run still fails after fetch_page's own retries, try the whole job again later.
# Safe because ingest is idempotent: a rerun skips what is already stored.
INGEST_RETRY_INTERVALS_S = [60, 300, 900]


def get_queue() -> Queue:
    # RQ is synchronous, so this is redis.Redis, not the asyncio client the API uses.
    return Queue(QUEUE_NAME, connection=Redis.from_url(get_settings().redis_url))


def enqueue_ingest(category: str, since: datetime, queue: Queue | None = None) -> Job:
    queue = queue or get_queue()
    return queue.enqueue(
        # By dotted path, not the function object: under `python -m app.jobs.ingest` the
        # function's module is "__main__", a name the worker could not import.
        "app.jobs.ingest.ingest",
        category,
        since,
        job_timeout=INGEST_TIMEOUT_S,
        retry=Retry(max=len(INGEST_RETRY_INTERVALS_S), interval=INGEST_RETRY_INTERVALS_S),
    )
