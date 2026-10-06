import asyncio
import logging
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime

import httpx2
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.arxiv import ArxivPaper, fetch_page

logger = logging.getLogger(__name__)

# arXiv's API terms ask for no more than one request every three seconds.
REQUEST_DELAY_S = 3.0


async def upsert_papers(session: AsyncSession, papers: Sequence[ArxivPaper]) -> int:
    """Insert papers we don't have yet; returns how many were new. The caller commits."""
    if not papers:
        return 0

    stmt = (
        insert(Paper)
        .values([asdict(paper) for paper in papers])
        # Papers already stored keep the version we saw first (see DECISIONS.md).
        .on_conflict_do_nothing(index_elements=[Paper.arxiv_id])
        # RETURNING only yields rows that were actually inserted, so skipped ones aren't counted.
        .returning(Paper.id)
    )
    result = await session.execute(stmt)
    return len(result.all())


async def ingest_category(
    client: httpx2.AsyncClient,
    session: AsyncSession,
    category: str,
    since: datetime,
    page_size: int = 100,
) -> int:
    """Store papers in `category` submitted at or after `since`; returns how many were new."""
    inserted = 0
    start = 0
    while True:
        papers = await fetch_page(client, category, start, page_size)
        if not papers:
            break

        new = await upsert_papers(session, [p for p in papers if p.published_at >= since])
        # One commit per page: a failure later in the crawl keeps the pages already stored.
        await session.commit()
        inserted += new
        logger.info("ingest %s: start=%d fetched=%d new=%d", category, start, len(papers), new)

        # Pages come newest first, so once one reaches past `since` the rest are older still.
        if min(p.published_at for p in papers) < since:
            break

        start += page_size
        await asyncio.sleep(REQUEST_DELAY_S)
    return inserted
