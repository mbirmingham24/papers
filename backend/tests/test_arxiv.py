from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from app.services import arxiv
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


@pytest.fixture
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(arxiv, "RETRY_DELAYS_S", (0, 0, 0))


def _client(*outcomes: int | Exception) -> tuple[httpx2.AsyncClient, list[httpx2.Request]]:
    """A client answering successive requests with these status codes (or raising these errors)."""
    requests: list[httpx2.Request] = []
    remaining = list(outcomes)

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return httpx2.Response(outcome, content=FEED)

    return httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), requests


async def test_fetch_page_retries_transient_failures(no_backoff: None) -> None:
    client, requests = _client(503, httpx2.ConnectError("refused"), 429, 200)

    papers = await fetch_page(client, "cs.LG", start=0, max_results=50)

    assert len(papers) == 2
    assert len(requests) == 4


async def test_fetch_page_gives_up_after_last_retry(no_backoff: None) -> None:
    client, requests = _client(503, 503, 503, 503)

    with pytest.raises(httpx2.HTTPStatusError):
        await fetch_page(client, "cs.LG", start=0, max_results=50)

    assert len(requests) == 4  # first try + one per entry in RETRY_DELAYS_S


async def test_fetch_page_does_not_retry_client_errors(no_backoff: None) -> None:
    client, requests = _client(400)

    with pytest.raises(httpx2.HTTPStatusError):
        await fetch_page(client, "cs.LG", start=0, max_results=50)

    assert len(requests) == 1


def _status_error(status: int) -> httpx2.HTTPStatusError:
    request = httpx2.Request("GET", API_URL)
    return httpx2.HTTPStatusError(
        str(status), request=request, response=httpx2.Response(status, request=request)
    )


def test_rate_limit_waits_much_longer_than_other_failures() -> None:
    assert arxiv._wait_s(_status_error(503), 3.0) == 3.0
    assert arxiv._wait_s(httpx2.ReadTimeout("slow"), 3.0) == 3.0
    assert arxiv._wait_s(_status_error(429), 3.0) == 60.0
