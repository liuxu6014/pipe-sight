"""The real collector IDs are available by default; execution uses new content."""

from datetime import timedelta

import pytest
from intelligence import test_collection_rollout as collection_support
from intelligence.test_collection_rollout import NOW, enqueue, execute, source

env = collection_support.env
from sqlalchemy import select


def test_default_registry_contains_existing_real_collectors_and_separates_types(env) -> None:
    registry = env.collection.ADAPTERS
    assert registry.get('pipechina_group_news').source_types == ('website',)
    assert registry.get('crossref_works').source_types == ('paper',)
    assert not registry.get('pipechina_group_news').supports_resume
    assert not registry.get('crossref_works').supports_resume


@pytest.mark.asyncio
async def test_registration_does_not_create_or_reactivate_admin_sources(env) -> None:
    e = env
    assert (await e.service.list_sources(e.db))['total'] == 0
    s = await source(e, is_enabled=False, name='管理员保留来源')
    listing = await e.service.list_sources(e.db)
    assert listing['total'] == 1 and listing['rows'][0]['name'] == '管理员保留来源'
    assert listing['rows'][0]['id'] == s['id']
    assert listing['rows'][0]['isEnabled'] is False
    assert not e.state.calls


@pytest.mark.asyncio
async def test_empty_configured_source_is_success_without_fabricated_article(env) -> None:
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    run = await e.repo.run(e.db, r['id'])
    assert (run.fetched_count, run.saved_count, run.failed_count) == (0, 0, 0)
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
async def test_article_processing_uses_new_fields_without_review_or_handoff(env) -> None:
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
async def test_news_summary_persists_and_recollection_without_enrichment_preserves_it(env) -> None:
    e = env
    registered = await source(e)
    configured = await e.repo.source(e.db, registered['id'])
    record = {
        'title': '管道检测试验',
        'url': 'https://example.test/summary',
        'content': '研究机构介绍管道检测方法与试验。' * 20,
        'summary': '研究机构介绍管道检测方法与试验。' * 11 + '应用效果仍需验证。',
    }
    assert 180 <= len(record['summary']) <= 220
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    article = e.db.sync.scalars(select(e.content.PipelineArticle)).one()
    assert article.summary == record['summary'] and article.content == record['content']
    summary = record.pop('summary')
    record['content'] += '补充原文内容。'
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    assert article.summary == summary
    record['summary'] = '摘' * 240
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    assert article.summary == summary


@pytest.mark.parametrize('kind', ['website', 'paper'])
@pytest.mark.asyncio
async def test_core_entities_persist_and_unavailable_or_excessive_results_do_not_wipe_them(env, kind) -> None:
    e = env
    registered = await source(e, type=kind)
    configured = await e.repo.source(e.db, registered['id'])
    body_field = 'abstract' if kind == 'paper' else 'content'
    record = {
        'title': '超声导波管道检测',
        'url': 'https://example.test/core',
        body_field: '超声导波；' + '、'.join(f'技术{i}' for i in range(8)),
        'entities': [{'type': '技术', 'name': '超声导波'}],
    }
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    model = e.content.PipelinePaper if kind == 'paper' else e.content.PipelineArticle
    saved = e.db.sync.scalars(select(model)).one()
    expected = record.pop('entities')
    assert saved.entities == expected
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    assert saved.entities == expected
    record['entities'] = [{'type': '技术', 'name': f'技术{i}'} for i in range(8)]
    await e.persistence.CollectionPersistenceService.save_record(e.db, configured, record, NOW)
    await e.db.commit()
    assert saved.entities == expected


@pytest.mark.asyncio
async def test_retry_persists_idempotently_and_does_not_overwrite_parent_failure(env) -> None:
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
