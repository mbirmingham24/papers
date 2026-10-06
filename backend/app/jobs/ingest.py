"""Ingest job: pull recent papers in one arXiv category into Postgres.

Run from the command line:  python -m app.jobs.ingest cs.LG --days 7
"""

import argparse
import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx2
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.services.ingest import ingest_category

logger = logging.getLogger(__name__)

# arXiv can take several seconds to build a page; httpx's 5 s default gives up too early.
HTTP_TIMEOUT_S = 30


async def _ingest(category: str, since: datetime) -> int:
    # Its own engine rather than app.core.db's: asyncio.run() below starts a fresh event loop
    # per call, and pooled connections can't outlive the loop that opened them.
    engine = create_async_engine(get_settings().database_url)
    try:
        async with (
            httpx2.AsyncClient(timeout=HTTP_TIMEOUT_S) as client,
            async_sessionmaker(engine)() as session,
        ):
            return await ingest_category(client, session, category, since)
    finally:
        await engine.dispose()


def ingest(category: str, since: datetime) -> int:
    """Sync entry point (what a scheduler or queue calls); returns how many papers were new."""
    inserted = asyncio.run(_ingest(category, since))
    logger.info("ingest %s since %s: %d new papers", category, since.date(), inserted)
    return inserted


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest recent arXiv papers in one category.")
    parser.add_argument("category", help="arXiv category, e.g. cs.LG")
    parser.add_argument("--days", type=int, default=7, help="how far back to go (default: 7)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ingest(args.category, datetime.now(UTC) - timedelta(days=args.days))


if __name__ == "__main__":
    main()
