"""Paper source date retains its real precision, independent of ingestion."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.intelligence.models.content import PipelinePaper
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.catalog import IntelligenceCatalogService


@pytest.mark.parametrize('published_date', ['2024-03-18', '2024-03', '2020', None])
@pytest.mark.parametrize('detail', [False, True])
def test_paper_preserves_source_date_precision(published_date: str | None, detail: bool) -> None:
    paper = PipelinePaper(
        id=2001,
        title='日期回归',
        published_date=published_date,
        created_at=datetime(2026, 10, 14),
        abstract='原文摘要',
        is_pushed=False,
    )
    row = IntelligenceCatalogService.paper_dict(paper, detail=detail, date_formatter=str)
    assert row['publish_time'] == (published_date or '')
    assert row['publication_year'] == (int(published_date[:4]) if published_date else None)
    assert paper.created_at == datetime(2026, 10, 14)


@pytest.mark.asyncio
async def test_latest_papers_order_source_date_before_database_limit() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = AsyncMock()
    db.execute.return_value = result
    await ContentDao.list_papers(db, limit=5)
    sql = str(
        db.execute.await_args.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={'literal_binds': True},
        )
    )
    ordering = sql.split('ORDER BY')[1]
    assert 'published_date' in ordering and 'created_at' not in ordering
    assert 'papers.id DESC' in ordering and 'LIMIT 5' in ordering


def test_paper_date_range_uses_partial_date_precision_not_ingestion() -> None:
    query, _, _ = ContentDao.query(
        PipelinePaper,
        published_from=datetime(2024, 3, 18),
        published_to=datetime(2024, 4, 20),
    )
    sql = str(query.compile(compile_kwargs={'literal_binds': True}))
    where = sql.split('WHERE')[1]
    assert 'length(papers.published_date)' in where
    assert 'created_at' not in where
