from collections.abc import Sequence
from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.services.arxiv import ArxivPaper


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
