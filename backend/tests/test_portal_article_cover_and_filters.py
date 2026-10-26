"""Canonical article details omit retired covers; source/category filters persist."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.intelligence.api.controller import catalog_tags_adapter, list_pipeline_intelligence
from app.intelligence.models.collection import PipelineSource
from app.intelligence.models.content import PipelineArticle, PipelineCategory, PipelinePaper
from app.intelligence.repositories.content_repository import ContentDao
from app.intelligence.services.catalog import IntelligenceCatalogService

PAPER_TOTAL = 7
CANDIDATE_LIMIT = 10
UNPROCESSABLE = 422


def article() -> PipelineArticle:
    return PipelineArticle(
        id=1001,
        title='真实资讯',
        source_id=101,
        source=PipelineSource(id=101, name='网站', type='website', adapter='website'),
        category_id=501,
        category=PipelineCategory(id=501, name='检测技术', prompt='分类', applies_to='news'),
        published_at=datetime(2026, 10, 14),
        content='原文',
        content_zh='译文',
        url='https://example.test/article',
        is_pushed=False,
    )


@pytest.mark.parametrize('detail', [False, True])
def test_article_uses_canonical_fields_without_cover_or_fulltext_metadata(detail: bool) -> None:
    item = article()
    item.metadata_json = {'authorized_full_text': {'asset_key': '../backup', 'images': [{}]}}
    row = IntelligenceCatalogService.article_dict(item, detail=detail, date_formatter=str)
    assert row['category'] == row['source_type'] == 'news'
    assert row['category_id'] == '501' and row['tags'] == ['检测技术']
    assert row['publish_time'] == '2026-10-14 00:00:00'
    assert row['summary'] == '译文'
    assert not {'cover_image', 'body_blocks', 'full_text', 'metadata_json', 'review_status'} & row.keys()
    if detail:
        assert row['content'] == '译文' and row['content_original'] == '原文'


def test_article_has_no_review_or_cover_storage() -> None:
    assert not {'review_status', 'permission_scope', 'metadata_json', 'article_type', 'tags'} & set(
        PipelineArticle.__table__.c.keys()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('category', 'tag', 'source_type', 'article_type', 'category_id'),
    [
        ('news', '检测技术', None, 'news', None),
        ('检测技术', None, 'wechat', 'wechat', '检测技术'),
        ('检测技术', '管道安全', 'news', 'news', '检测技术'),
    ],
)
async def test_category_and_source_are_independent_filters(
    monkeypatch: pytest.MonkeyPatch,
    category: str,
    tag: str | None,
    source_type: str | None,
    article_type: str,
    category_id: str | None,
) -> None:
    rows, count = AsyncMock(return_value=[]), AsyncMock(return_value=0)
    monkeypatch.setattr(ContentDao, 'list_articles', rows)
    monkeypatch.setattr(ContentDao, 'count_articles', count)
    await IntelligenceCatalogService.list_intelligence(
        None,
        category=category,
        tag=tag,
        source_type=source_type,
        keyword=None,
        page_num=1,
        page_size=10,
        date_formatter=str,
    )
    for call in (rows.await_args, count.await_args):
        assert call.kwargs['article_type'] == article_type
        assert call.kwargs['category_id'] == category_id
        assert call.kwargs['tag'] == tag


def test_portal_news_filter_maps_to_website_source_in_sql() -> None:
    query, _, _ = ContentDao.query(PipelineArticle, article_type='news', category_id=501)
    sql = str(query.compile(compile_kwargs={'literal_binds': True}))
    assert "data_sources.type = 'website'" in sql
    assert 'categories.id = 501' in sql


@pytest.mark.asyncio
async def test_paper_category_filter_limits_rows_and_total(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, count = AsyncMock(return_value=[]), AsyncMock(return_value=7)
    monkeypatch.setattr(ContentDao, 'list_papers', rows)
    monkeypatch.setattr(ContentDao, 'count_papers', count)
    result = await IntelligenceCatalogService.list_intelligence(
        None,
        category='paper',
        tag='完整性',
        source_type=None,
        keyword=None,
        page_num=1,
        page_size=10,
        date_formatter=str,
    )
    assert result['total'] == PAPER_TOTAL
    assert rows.await_args.kwargs['tag'] == count.await_args.kwargs['tag'] == '完整性'
    query, _, _ = ContentDao.query(PipelinePaper, tag='完整性')
    assert 'categories.name' in str(query)


@pytest.mark.asyncio
async def test_multi_category_route_passes_filters_to_rows_and_count(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, count = AsyncMock(return_value=[]), AsyncMock(return_value=7)
    monkeypatch.setattr(ContentDao, 'list_articles', rows)
    monkeypatch.setattr(ContentDao, 'count_articles', count)
    await list_pipeline_intelligence(
        None,
        None,
        category='article',
        source_type='wechat',
        tags='["智能巡检","管道安全"]',
        page_num=2,
        page_size=5,
    )
    for call in (rows.await_args, count.await_args):
        assert call.kwargs['tags'] == ['智能巡检', '管道安全']
        assert call.kwargs['article_type'] == 'wechat'
    assert rows.await_args.kwargs['limit'] == CANDIDATE_LIMIT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'payload',
    [
        'not-json',
        '"智能巡检"',
        '[1]',
        '[""]',
        '["' + '长' * 101 + '"]',
        str(['x'] * 21).replace("'", '"'),
    ],
)
async def test_category_route_rejects_malformed_or_unbounded_values(payload: str) -> None:
    with pytest.raises(HTTPException) as error:
        await list_pipeline_intelligence(None, None, tags=payload)
    assert error.value.status_code == UNPROCESSABLE


def test_category_validation_accepts_chinese_array() -> None:
    assert catalog_tags_adapter.validate_json('["智能巡检","管道安全"]') == ['智能巡检', '管道安全']
