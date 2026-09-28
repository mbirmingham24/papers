from datetime import UTC, datetime
from pathlib import Path

import httpx2

from app.services.arxiv import API_URL, ArxivPaper, fetch_page, parse_feed

FEED = (Path(__file__).parent / "fixtures" / "arxiv_feed.xml").read_bytes()


def test_parse_feed() -> None:
    papers = parse_feed(FEED)

    assert papers == [
        ArxivPaper(
            arxiv_id="2409.01234",  # version suffix stripped
            title="Attention Is Still All You Need",  # hard wrap collapsed
            abstract="We revisit attention. Results are mixed.",
            authors=["Ada Lovelace", "Alan Turing"],
            categories=["cs.AI", "cs.LG"],  # declared primary first, whatever the feed order
            published_at=datetime(2024, 9, 2, 17, 59, 59, tzinfo=UTC),
        ),
        ArxivPaper(
            arxiv_id="hep-th/9901001",  # old-style id keeps its slash
            title="An Old-Style Identifier",
            abstract="Short.",
            authors=["Emmy Noether"],
            categories=["hep-th"],
            published_at=datetime(1999, 1, 1, tzinfo=UTC),
        ),
    ]


def test_parse_feed_with_no_entries() -> None:
    assert parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>') == []


async def test_fetch_page_sends_query_and_parses_response() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, content=FEED)

    async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
        papers = await fetch_page(client, "cs.LG", start=100, max_results=50)

    assert [p.arxiv_id for p in papers] == ["2409.01234", "hep-th/9901001"]
    (request,) = requests
    assert str(request.url).startswith(API_URL)
    assert dict(request.url.params) == {
        "search_query": "cat:cs.LG",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": "100",
        "max_results": "50",
    }
