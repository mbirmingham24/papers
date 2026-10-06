"""Client for the arXiv export API (Atom feed): https://info.arxiv.org/help/api/user-manual.html"""

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import httpx2

logger = logging.getLogger(__name__)

API_URL = "https://export.arxiv.org/api/query"

# Wait before each retry, doubling every time; a page is tried once more than this has entries.
RETRY_DELAYS_S: tuple[float, ...] = (3.0, 6.0, 12.0)

# Feed elements live in XML namespaces; ElementTree needs the prefix in every lookup.
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# "http://arxiv.org/abs/2409.01234v2" -> "2409.01234"; also old-style "hep-th/9901001v1".
_ID_RE = re.compile(r"arxiv\.org/abs/(?P<id>.+?)v\d+$")


@dataclass(frozen=True)
class ArxivPaper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]  # primary category first
    published_at: datetime  # submission time of v1, UTC


def _clean(text: str | None) -> str:
    # The feed hard-wraps titles and abstracts; collapse that into single spaces.
    return " ".join((text or "").split())


def _parse_entry(entry: ET.Element) -> ArxivPaper:
    raw_id = entry.findtext("atom:id", "", _NS)
    match = _ID_RE.search(raw_id)
    if match is None:
        raise ValueError(f"unexpected arXiv id: {raw_id!r}")

    primary = entry.find("arxiv:primary_category", _NS)
    categories = [c.attrib["term"] for c in entry.findall("atom:category", _NS)]
    if primary is not None:
        # <category> order isn't documented, so put the declared primary first explicitly.
        term = primary.attrib["term"]
        categories = [term] + [c for c in categories if c != term]

    return ArxivPaper(
        arxiv_id=match["id"],
        title=_clean(entry.findtext("atom:title", None, _NS)),
        abstract=_clean(entry.findtext("atom:summary", None, _NS)),
        authors=[
            _clean(a.findtext("atom:name", None, _NS)) for a in entry.findall("atom:author", _NS)
        ],
        categories=categories,
        published_at=datetime.fromisoformat(entry.findtext("atom:published", "", _NS)),
    )


def parse_feed(xml: bytes) -> list[ArxivPaper]:
    root = ET.fromstring(xml)
    return [_parse_entry(entry) for entry in root.findall("atom:entry", _NS)]


def _is_retryable(exc: httpx2.HTTPError) -> bool:
    if isinstance(exc, httpx2.HTTPStatusError):
        # 429 and 5xx are the server asking us to come back later; other 4xx mean the
        # request itself is wrong, and sending it again won't change the answer.
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    # Timeouts, refused or dropped connections.
    return isinstance(exc, httpx2.TransportError)


async def fetch_page(
    client: httpx2.AsyncClient, category: str, start: int, max_results: int
) -> list[ArxivPaper]:
    """One page of `category`, newest submissions first. Retries transient failures."""
    params = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": start,
        "max_results": max_results,
    }
    # The trailing None is the last attempt: nothing left to wait for, so the error propagates.
    for delay in (*RETRY_DELAYS_S, None):
        try:
            response = await client.get(API_URL, params=params)
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            if delay is None or not _is_retryable(exc):
                raise
            logger.warning("arxiv: start=%d failed (%r), retrying in %.0f s", start, exc, delay)
            await asyncio.sleep(delay)
        else:
            return parse_feed(response.content)
    raise AssertionError("unreachable")
