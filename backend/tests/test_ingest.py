from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services import ingest
from app.services.arxiv import parse_feed
from app.services.ingest import ingest_category, upsert_papers

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


def _feed(*entries: tuple[str, str]) -> bytes:
    """A minimal Atom feed with one entry per (arxiv_id, published) pair."""
    body = "".join(
        f"<entry><id>http://arxiv.org/abs/{arxiv_id}v1</id><published>{published}</published>"
        f"<title>Paper {arxiv_id}</title><summary>Abstract.</summary>"
        '<author><name>Ada Lovelace</name></author><category term="cs.LG"/></entry>'
        for arxiv_id, published in entries
    )
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'.encode()


# Newest first, two per page, like the real API with max_results=2.
PAGES = {
    0: _feed(("2410.00004", "2024-10-04T00:00:00Z"), ("2410.00003", "2024-10-03T00:00:00Z")),
    2: _feed(("2410.00002", "2024-10-02T00:00:00Z"), ("2410.00001", "2024-10-01T00:00:00Z")),
}


@pytest.fixture
def arxiv() -> tuple[httpx2.AsyncClient, list[int]]:
    """A client served from PAGES, plus the `start` offset of every request it received."""
    starts: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        start = int(request.url.params["start"])
        starts.append(start)
        return httpx2.Response(200, content=PAGES.get(start, _feed()))

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), starts


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "REQUEST_DELAY_S", 0)


async def test_ingest_pages_until_feed_is_empty(
    db_session: AsyncSession, arxiv: tuple[httpx2.AsyncClient, list[int]]
) -> None:
    client, starts = arxiv
    since = datetime(2024, 1, 1, tzinfo=UTC)

    assert await ingest_category(client, db_session, "cs.LG", since, page_size=2) == 4
    assert starts == [0, 2, 4]
    assert await _count(db_session) == 4


async def test_ingest_stops_at_since(
    db_session: AsyncSession, arxiv: tuple[httpx2.AsyncClient, list[int]]
) -> None:
    client, starts = arxiv
    # Cuts page two in half: 2410.00002 is exactly at the boundary and kept, 2410.00001 is not.
    since = datetime(2024, 10, 2, tzinfo=UTC)

    assert await ingest_category(client, db_session, "cs.LG", since, page_size=2) == 3
    assert starts == [0, 2]  # no request past the page that crossed `since`
    stored = await db_session.scalars(select(Paper.arxiv_id).order_by(Paper.arxiv_id))
    assert stored.all() == ["2410.00002", "2410.00003", "2410.00004"]


async def test_ingest_rerun_adds_no_rows(
    db_session: AsyncSession, arxiv: tuple[httpx2.AsyncClient, list[int]]
) -> None:
    client, _ = arxiv
    since = datetime(2024, 1, 1, tzinfo=UTC)

    assert await ingest_category(client, db_session, "cs.LG", since, page_size=2) == 4
    assert await ingest_category(client, db_session, "cs.LG", since, page_size=2) == 0
    assert await _count(db_session) == 4
