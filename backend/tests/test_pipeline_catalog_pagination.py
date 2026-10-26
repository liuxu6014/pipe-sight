"""Canonical catalog pagination and SQL filtering, without external services."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.intelligence.models.content import PipelineArticle, PipelinePaper
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.catalog import IntelligenceCatalogService
from exceptions.exception import ServiceException

CATALOG_TOTAL = 1000
CANDIDATE_LIMIT = 4


def article(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=1000 + index,
        title=f'资讯 {index}',
        source=SimpleNamespace(type='website', name='来源'),
        category=None,
        category_id=None,
        published_at=datetime(2026, 8, 10 - index),
        content='正文',
        content_zh=None,
        author=None,
        url='https://example.test',
        is_pushed=False,
    )


@pytest.mark.asyncio
async def test_article_catalog_includes_all_sources_without_synthetic_category(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, count, papers = AsyncMock(return_value=[]), AsyncMock(return_value=7), AsyncMock()
    monkeypatch.setattr(ContentDao, 'list_articles', rows)
    monkeypatch.setattr(ContentDao, 'count_articles', count)
    monkeypatch.setattr(ContentDao, 'list_papers', papers)
    result = await IntelligenceCatalogService.list_intelligence(
        None,
        category='article',
        keyword=None,
        source_type=None,
        page_num=1,
        page_size=5,
        date_formatter=str,
    )
    assert result == {'rows': [], 'total': 7}
    assert rows.await_args.kwargs['article_type'] is None
    assert rows.await_args.kwargs['category_id'] is None
    papers.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_reads_bounded_candidates_and_full_database_count(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, count = AsyncMock(return_value=[article(i) for i in range(4)]), AsyncMock(return_value=1000)
    monkeypatch.setattr(ContentDao, 'list_articles', rows)
    monkeypatch.setattr(ContentDao, 'count_articles', count)
    result = await IntelligenceCatalogService.list_intelligence(
        None,
        category='news',
        keyword='应力',
        source_type=None,
        page_num=2,
        page_size=2,
        date_formatter=lambda value: value.isoformat(),
    )
    assert [row['id'] for row in result['rows']] == ['1002', '1003']
    assert result['total'] == CATALOG_TOTAL
    assert rows.await_args.kwargs['offset'] == 0
    assert rows.await_args.kwargs['limit'] == CANDIDATE_LIMIT
    for call in (rows.await_args, count.await_args):
        assert call.kwargs['keyword'] == '应力'
        assert call.kwargs['article_type'] == 'news'


def test_queries_filter_canonical_source_category_text_and_dates() -> None:
    article_query, _, _ = ContentDao.query(
        PipelineArticle,
        article_type='wechat',
        category_id='501',
        keyword='应力',
        published_from=datetime(2026, 9, 25),
        published_to=datetime(2026, 10, 2),
    )
    sql = str(article_query.compile(compile_kwargs={'literal_binds': True}))
    assert "data_sources.type = 'wechat'" in sql
    assert 'categories.id = 501' in sql
    assert "news_articles.published_at >= '2026-09-25" in sql
    assert "news_articles.published_at <= '2026-10-02" in sql
    assert 'news_articles.content_zh' in sql and 'ESCAPE' in sql
    assert 'review_status' not in sql and 'permission_scope' not in sql
    paper_query, _, _ = ContentDao.query(
        PipelinePaper,
        year_from=2024,
        year_to=2026,
        journal='JPSE',
        directions=['完整性'],
    )
    sql = str(paper_query.compile(compile_kwargs={'literal_binds': True}))
    assert "left(papers.published_date, 4) >= '2024'" in sql
    assert "left(papers.published_date, 4) <= '2026'" in sql
    assert 'papers.journal' in sql and 'categories.name IN' in sql
    assert 'review_status' not in sql and 'metadata_json' not in sql


@pytest.mark.asyncio
async def test_article_cursor_range_and_page_are_applied_in_database() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    await ContentDao.list_articles(
        db,
        keyword='应力',
        search_after=(4, datetime(2026, 10, 2), 'news', 1001),
        limit=2,
    )
    sql = str(db.execute.await_args.args[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'news_articles.id < 1001' in sql
    assert 'news_articles.published_at' in sql
    assert 'ORDER BY' in sql and 'LIMIT 2' in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(('page', 'size'), [(0, 10), (1, 0), (1, 101)])
async def test_catalog_rejects_invalid_pagination(page: int, size: int) -> None:
    with pytest.raises(ServiceException):
        await IntelligenceCatalogService.list_intelligence(
            None,
            category='article',
            keyword=None,
            source_type=None,
            page_num=page,
            page_size=size,
            date_formatter=str,
        )


@pytest.mark.asyncio
async def test_missing_public_detail_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ContentDao, 'get_article', AsyncMock(return_value=None))
    monkeypatch.setattr(ContentDao, 'get_paper', AsyncMock(return_value=None))
    with pytest.raises(ServiceException):
        await IntelligenceCatalogService.get_detail(None, '999999', date_formatter=str)


@pytest.mark.asyncio
async def test_unclassified_article_is_readable_without_review(monkeypatch: pytest.MonkeyPatch) -> None:
    item = article(0)
    monkeypatch.setattr(ContentDao, 'get_article', AsyncMock(return_value=item))
    result = await IntelligenceCatalogService.get_detail(None, item.id, date_formatter=str)
    assert result['category_id'] is None and result['tags'] == []
    assert result['content'] == '正文'
    assert 'review_status' not in result
