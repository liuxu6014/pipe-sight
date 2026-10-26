"""The real collector IDs are available by default; execution uses new content."""

from datetime import timedelta

import pytest
from intelligence import test_collection_rollout as collection_support
from intelligence.test_collection_rollout import NOW, enqueue, execute, source

env = collection_support.env
from sqlalchemy import select


def test_default_registry_contains_existing_real_collectors_and_separates_types(env):
    registry = env.collection.ADAPTERS
    assert registry.get('pipechina_group_news').source_types == ('website',)
    assert registry.get('crossref_works').source_types == ('paper',)
    assert not registry.get('pipechina_group_news').supports_resume
    assert not registry.get('crossref_works').supports_resume


@pytest.mark.asyncio
async def test_registration_does_not_create_or_reactivate_admin_sources(env):
    e = env
    assert (await e.service.list_sources(e.db))['total'] == 0
    s = await source(e, is_enabled=False, name='管理员保留来源')
    listing = await e.service.list_sources(e.db)
    assert listing['total'] == 1 and listing['rows'][0]['name'] == '管理员保留来源'
    assert listing['rows'][0]['id'] == s['id']
    assert listing['rows'][0]['isEnabled'] is False
    assert not e.state.calls


@pytest.mark.asyncio
async def test_empty_configured_source_is_success_without_fabricated_article(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    run = await e.repo.run(e.db, r['id'])
    assert (run.fetched_count, run.saved_count, run.failed_count) == (0, 0, 0)
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
async def test_article_processing_uses_new_fields_without_review_or_handoff(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    e.state.batches = [
        e.batch(
            [{'title': '新闻原文', 'url': 'https://example.test/article', 'content': '采集正文', 'author': None}], {}
        )
    ]
    assert (await execute(e, r['id']))['status'] == 'success'
    article = e.db.sync.scalars(select(e.content.PipelineArticle)).one()
    assert article.source_id == int(s['id']) and article.content == '采集正文'
    assert article.published_at is None and article.is_pushed is False
    assert not hasattr(article, 'review_status') and not hasattr(article, 'handoff_status')


@pytest.mark.asyncio
async def test_retry_persists_idempotently_and_does_not_overwrite_parent_failure(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    record = {'title': '已保存', 'url': 'https://example.test/existing', 'content': '真实输入'}
    e.state.batches = [e.batch([record], {}), e.collection.TransientCollectionError()]
    assert (await execute(e, r['id']))['status'] == 'failed'
    retry = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    e.state.batches = [e.batch([record], {})]
    e.clock = lambda: NOW + timedelta(seconds=30)
    assert (await execute(e, retry['id']))['status'] == 'success'
    assert len(e.db.sync.scalars(select(e.content.PipelineArticle)).all()) == 1
    parent = await e.repo.run(e.db, r['id'])
    child = await e.repo.run(e.db, retry['id'])
    assert parent.status == 'failed' and parent.saved_count == 1 and parent.error
    assert child.status == 'success' and child.saved_count == 0
