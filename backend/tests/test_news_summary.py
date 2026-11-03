"""Summaries are generated separately, validated and shared by list/detail."""

import json
from types import SimpleNamespace

import pytest
from test_news_entity_extraction import Database, model

from app.intelligence.services.catalog import IntelligenceCatalogService
from app.intelligence.services.entities import EntityExtractionService, validated_summary

SOURCE = '研究机构开展管道检测试验，介绍检测方法与应用场景。' * 20
SUMMARY = '研究机构开展管道检测试验。' * 14 + '相关方法仍需验证。'


@pytest.mark.parametrize('length', [180, 200, 220])
def test_accepts_approximately_two_hundred_characters(length):
    assert validated_summary('摘' * length, SOURCE) == '摘' * length


@pytest.mark.parametrize('value', ['摘' * 179, '摘' * 221, '', None, ['摘要']])
def test_invalid_length_is_rejected_instead_of_silently_truncated(value):
    assert validated_summary(value, SOURCE) is None


def test_short_original_is_not_padded_and_missing_body_is_not_invented():
    assert validated_summary('研究机构开展试验。', '研究机构开展管道检测试验。') == '研究机构开展试验。'
    assert validated_summary('摘' * 200, '短原文') is None
    assert validated_summary('新闻', '') is None


@pytest.mark.asyncio
async def test_summary_and_grounded_entities_share_one_model_request():
    calls = []

    async def gateway(db, snapshot, **kwargs):
        calls.append(kwargs)
        return json.dumps({'summary': SUMMARY, 'entities': [{'type': '机构', 'name': '研究机构'}]})

    result = await EntityExtractionService.enrich(
        Database([model()]), title='管道检测', content=SOURCE, gateway=gateway
    )
    assert 180 <= len(SUMMARY) <= 220
    assert result == {'summary': SUMMARY, 'entities': [{'type': '机构', 'name': '研究机构'}]}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_bad_summary_does_not_discard_valid_entities_or_overwrite_previous_summary():
    async def gateway(*args, **kwargs):
        return json.dumps({'summary': '摘' * 240, 'entities': []})

    result = await EntityExtractionService.enrich(
        Database([model()]), title='管道检测', content=SOURCE, gateway=gateway
    )
    assert result == {'entities': []}


def test_list_and_detail_return_same_stored_summary_never_body_prefix():
    article = SimpleNamespace(
        id=18,
        source=SimpleNamespace(type='website', name='来源'),
        category=None,
        category_id=None,
        title='标题',
        content=SOURCE,
        content_zh=None,
        summary=SUMMARY,
        published_at=None,
        url='https://example.invalid/news',
        author=None,
        entities=[],
        is_pushed=False,
    )
    listing = IntelligenceCatalogService.article_dict(article, date_formatter=str)
    detail = IntelligenceCatalogService.article_dict(article, detail=True, date_formatter=str)
    assert listing['summary'] == detail['summary'] == SUMMARY
    assert detail['content'] == SOURCE
    article.summary = None
    assert IntelligenceCatalogService.article_dict(article, date_formatter=str)['summary'] == ''
