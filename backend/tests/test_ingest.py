from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.arxiv import parse_feed
from app.services.ingest import upsert_papers

PAPERS = parse_feed((Path(__file__).parent / "fixtures" / "arxiv_feed.xml").read_bytes())


async def _count(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Paper)) or 0


async def test_upsert_inserts_new_papers(db_session: AsyncSession) -> None:
    assert await upsert_papers(db_session, PAPERS) == 2
    await db_session.commit()

    stored = await db_session.scalar(select(Paper).where(Paper.arxiv_id == "2409.01234"))
    assert stored is not None
    assert stored.title == "Attention Is Still All You Need"
    assert stored.authors == ["Ada Lovelace", "Alan Turing"]
    assert stored.categories == ["cs.AI", "cs.LG"]
    assert stored.published_at == PAPERS[0].published_at


async def test_upsert_is_idempotent(db_session: AsyncSession) -> None:
    assert await upsert_papers(db_session, PAPERS) == 2
    await db_session.commit()

    assert await upsert_papers(db_session, PAPERS) == 0
    await db_session.commit()
    assert await _count(db_session) == 2


async def test_upsert_skips_duplicates_within_one_batch(db_session: AsyncSession) -> None:
    # arXiv paging can repeat an entry across pages when new papers land mid-crawl.
    assert await upsert_papers(db_session, [PAPERS[0], PAPERS[0]]) == 1
    await db_session.commit()
    assert await _count(db_session) == 1


async def test_upsert_with_no_papers(db_session: AsyncSession) -> None:
    assert await upsert_papers(db_session, []) == 0
