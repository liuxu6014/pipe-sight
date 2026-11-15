"""One provider call produces persisted filtering, classification and enrichment."""

import importlib
import json
from copy import deepcopy

import pytest
import test_collection_translation as support
from sqlalchemy import select
from test_collection_rollout import NOW, enqueue, execute
from test_collection_translation import configured_source, record

env = support.env
translation = support.translation


@pytest.fixture(autouse=True)
def real_processing_admission(env, monkeypatch):
    monkeypatch.setattr(env.processing, 'freeze', env.real_processing_freeze)
    monkeypatch.setattr(env.processing, 'prepare', env.real_processing_prepare)


def output(**overrides):
    return json.dumps(
        {
            'filter': {'decision': 'keep', 'reason': '管道技术', 'evidence': '管道检测'},
            'category_id': None,
            'category_name': None,
            'summary': '研究机构开展管道检测试验。',
            'entities': [{'type': '机构', 'name': '研究机构'}, {'type': '技术', 'name': '管道检测'}],
            'aiInsight': None,
            **overrides,
        },
        ensure_ascii=False,
    )


async def configured(e, kind='website'):
    source, _model = await configured_source(e, kind=kind)
    # Translation and processing are independently selected, deliberately using two resources.
    model2 = e.ai_model(
        id=2,
        provider='compatible',
        code='processor',
        base_url='https://example.test/process',
        capabilities=['text_generate'],
        parameters={},
        is_enabled=True,
    )
    e.db.add(model2)
    e.db.add(e.config(key='pipeline.processing.modelId', value='2'))
    e.db.add(
        e.content.PipelineCategory(
            id=801, name='检测技术', prompt='保留管道检测', model_id=1, applies_to='all', is_enabled=True, sort_order=0
        )
    )
    await e.db.commit()
    return source


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['website', 'wechat', 'paper'])
async def test_same_processing_call_persists_summary_entities_and_category_after_translation(
    env, translation, monkeypatch, kind
):
    e = env
    source = await configured(e, kind)
    calls = []

    async def gateway(db, snapshot, **kwargs):
        calls.append((snapshot, kwargs))
        if kwargs['request_id'].startswith('collection-translation:'):
            return json.dumps(
                {'abstract_zh' if kind == 'paper' else 'content_zh': '研究机构开展管道检测试验，介绍管道检测技术。'},
                ensure_ascii=False,
            )
        assert snapshot['id'] == '2'
        assert '研究机构开展管道检测试验' in kwargs['prompt']
        assert '保留管道检测' in kwargs['system_prompt']
        return output(category_id='801', category_name='检测技术')

    monkeypatch.setattr(importlib.import_module('app.research.services.model_generation').ModelGateway, 'call', gateway)
    e.state.batches = [e.batch([record(kind)], {})]
    run = await enqueue(e, source['id'])
    frozen = deepcopy((await e.repo.run(e.db, run['id'])).config_snapshot)
    # Later selection/rule changes cannot alter this queued run.
    setting = e.db.sync.scalars(select(e.config).where(e.config.key == 'pipeline.processing.modelId')).one()
    setting.value = ''
    await e.db.commit()
    result = await execute(e, run['id'])
    assert result['status'] == 'success'
    assert len(calls) == 2 and calls[0][0]['id'] == '1' and calls[1][0]['id'] == '2'
    model = e.content.PipelinePaper if kind == 'paper' else e.content.PipelineArticle
    saved = e.db.sync.scalars(select(model)).one()
    assert saved.summary == '研究机构开展管道检测试验。'
    assert saved.category_id == 801
    assert saved.entities == [{'type': '机构', 'name': '研究机构'}, {'type': '技术', 'name': '管道检测'}]
    if kind == 'paper':
        assert saved.abstract == record(kind)['abstract']
    assert (await e.repo.run(e.db, run['id'])).config_snapshot == frozen


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'decision,saved_count,failed_count',
    [
        ('exclude', 0, 0),
        ('review', 1, 0),
        ('invalid', 0, 1),
        ('fabricated_exclusion', 0, 1),
        ('unknown_category', 0, 1),
    ],
)
async def test_filter_only_excludes_with_evidence_and_never_silently_drops_reviews(
    env, translation, decision, saved_count, failed_count
):
    e = env
    source = await configured(e)
    item = record()
    item['content'] = '研究机构开展管道检测试验。'
    item['content_zh'] = item['content']
    filtering = {'decision': decision, 'reason': '判断依据', 'evidence': '管道检测'}
    if decision == 'fabricated_exclusion':
        filtering = {'decision': 'exclude', 'reason': '无关', 'evidence': '原文没有的证据'}
    extra = {'category_id': '999', 'category_name': '伪造'} if decision == 'unknown_category' else {}
    if extra:
        filtering['decision'] = 'keep'
    e.state.category_reply = output(filter=filtering, **extra)
    e.state.batches = [e.batch([item], {})]
    run = await enqueue(e, source['id'])
    await execute(e, run['id'])
    persisted_run = await e.repo.run(e.db, run['id'])
    assert persisted_run.saved_count == saved_count and persisted_run.failed_count == failed_count
    assert len(e.db.sync.scalars(select(e.content.PipelineArticle)).all()) == saved_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'answer,code',
    [
        ('PRIVATE_RESPONSE not JSON', 'processing_json_invalid'),
        (output(filter=None), 'processing_filter_invalid'),
        (output(category_id='999', category_name='未知'), 'processing_category_invalid'),
        (output(entities=None), 'processing_entities_invalid'),
        (output(summary='PRIVATE_RESPONSE'), 'processing_summary_invalid'),
        (RuntimeError('PRIVATE_PROVIDER_KEY=do-not-disclose'), 'processing_model_call_failed'),
    ],
)
async def test_processing_failure_reports_safe_stage_without_disclosing_provider_or_article(
    env, translation, caplog, answer, code
):
    e = env
    source = await configured(e)
    item = record()
    item['content_zh'] = '研究机构开展管道检测试验。'
    item['_processing_error_code'] = 'PRIVATE_CANDIDATE_MARKER'
    e.state.category_reply = answer
    e.state.batches = [e.batch([item], {})]
    run = await enqueue(e, source['id'])
    with caplog.at_level('WARNING', logger='app.intelligence.services.content_processing'):
        assert (await execute(e, run['id']))['status'] == 'failed'
    persisted = await e.repo.run(e.db, run['id'])
    assert code in persisted.error and '重新试采' in persisted.error
    assert persisted.failed_count == 1 and persisted.saved_count == 0
    assert code in caplog.text
    for sensitive in ('PRIVATE_RESPONSE', 'PRIVATE_PROVIDER_KEY', 'PRIVATE_CANDIDATE_MARKER', item['content_zh']):
        assert sensitive not in persisted.error and sensitive not in caplog.text
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


def test_processing_diagnostics_never_echo_unknown_candidate_error_codes():
    from app.intelligence.services.processing_errors import processing_failure_message

    for value in ('PRIVATE_PROVIDER_KEY=secret', ['untrusted'], None):
        message = processing_failure_message(value)
        assert 'processing_failed' in message and 'PRIVATE_PROVIDER_KEY' not in message


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['website', 'paper'])
@pytest.mark.parametrize('missing', [None, '', '  \n  '])
async def test_missing_source_text_fails_before_any_paid_translation_or_processing_call(
    env, translation, kind, missing
):
    e = env
    source = await configured(e, kind)
    item = record(kind)
    field = 'abstract' if kind == 'paper' else 'content'
    item[field] = missing
    item.pop(field + '_zh', None)
    e.state.category_reply = RuntimeError('model must not be called without source evidence')
    e.state.batches = [e.batch([item], {})]
    run = await enqueue(e, source['id'])
    assert (await execute(e, run['id']))['status'] == 'failed'
    stored = await e.repo.run(e.db, run['id'])
    assert 'processing_input_missing' in stored.error
    assert stored.failed_count == 1 and stored.saved_count == 0
    assert not e.state.category_requests
    assert not e.db.sync.scalars(
        select(e.content.PipelinePaper if kind == 'paper' else e.content.PipelineArticle)
    ).all()


@pytest.mark.asyncio
async def test_unconfigured_processing_does_not_fall_back_to_source_or_sole_model(env, translation):
    e = env
    source, _ = await configured_source(e)
    item = record()
    item['content_zh'] = '已有中文正文'
    e.state.batches = [e.batch([item], {})]
    with pytest.raises(e.collection.ConfigurationError, match='尚未配置内容处理模型'):
        await enqueue(e, source['id'])
    assert e.state.category_requests == []
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert not await e.repo.history(e.db)


@pytest.mark.asyncio
async def test_old_unconfigured_snapshot_fails_and_fresh_run_recovers_after_configuration(env, translation):
    e = env
    source = await configured(e)
    run = await enqueue(e, source['id'])
    saved_run = await e.repo.run(e.db, run['id'])
    saved_run.config_snapshot = {**saved_run.config_snapshot, 'processing_model': None}
    await e.db.commit()
    item = record()
    item['content_zh'] = '研究机构开展管道检测试验。'
    e.state.batches = [e.batch([item], {})]
    assert (await execute(e, run['id']))['status'] == 'failed'
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    e.state.category_reply = output()
    recovered = await enqueue(e, source['id'], request_id='manual:fixed-processing')
    assert (await execute(e, recovered['id']))['status'] == 'success'
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().summary


@pytest.mark.asyncio
async def test_two_global_settings_are_independent_and_category_uses_processing_choice(env, translation):
    e = env
    await configured(e)
    settings = importlib.import_module('app.intelligence.services.translation_settings')
    assert await settings.processing_settings(e.db) == {'modelId': '2'}
    await settings.save_translation_settings(e.db, None)
    assert await settings.processing_settings(e.db) == {'modelId': '2'}
    categories = importlib.import_module('app.intelligence.services.categories').CategoryService

    # Existing compatibility FK is updated from global processing config, never caller's arbitrary model.
    async def refresh(row):
        e.db.sync.refresh(row)
        row.created_at = row.updated_at = NOW

    e.db.refresh = refresh
    result = await categories.save(
        e.db,
        {
            'name': '新类别',
            'prompt': '分类要求',
            'model_id': 1,
            'applies_to': 'news',
            'is_enabled': True,
            'sort_order': 0,
        },
    )
    assert result['modelId'] == 2
    await settings.save_processing_settings(e.db, None)
    assert await settings.translation_settings(e.db) == {'modelId': None}


@pytest.mark.asyncio
async def test_cancelling_during_the_combined_call_never_writes_partial_results(env, translation):
    import asyncio

    from test_collection_rollout import AsyncMemorySession

    e = env
    source = await configured(e)
    item = record()
    item['content_zh'] = '研究机构开展管道检测试验。'
    run = await enqueue(e, source['id'])
    cleaned = []

    async def waiting(db):
        await db.rollback()
        async with AsyncMemorySession(e.engine) as other:
            assert (await e.service.stop_collection_run(other, run['id'], clock=e.clock))['status'] == 'stopping'
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.append(True)

    e.state.category_reply = waiting
    e.state.batches = [e.batch([item], {})]
    result = await e.collection.PipelineCollectionService.execute(
        e.db, run['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.005
    )
    assert result['status'] == 'cancelled' and cleaned
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize('decision,expected', [('keep', 'inserted'), ('exclude', 'skipped')])
async def test_kafka_handler_uses_the_same_processing_contract_before_persistence(env, translation, decision, expected):
    # Execute the actual entrypoint with transport/registry boundaries replaced;
    # no broker or production-only database is contacted.
    import ast
    import logging
    from pathlib import Path

    from sqlalchemy.exc import IntegrityError
    from test_collection_rollout import AsyncMemorySession

    e = env
    selected = await configured(e)
    e.db.bind = e.engine
    source = await e.repo.source(e.db, selected['id'])
    await e.db.commit()
    item = record()
    item['content_zh'] = '研究机构开展管道检测试验。'
    e.state.category_reply = output(filter={'decision': decision, 'reason': '依据', 'evidence': '管道检测'})

    async def ensure_source(*args):
        return source

    module_path = Path(__file__).resolve().parents[2] / 'src/app/intelligence/tasks/kafka_content_consumer.py'  # noqa: ASYNC240
    tree = ast.parse(module_path.read_text())
    function = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == '_process_and_save'
    )
    scope = {
        'KafkaContentMessage': object,
        '_ensure_source': ensure_source,
        '_to_record': lambda message: deepcopy(item),
        'wire_id': str,
        'async_sessionmaker': lambda **kwargs: lambda: AsyncMemorySession(e.engine),
        'CollectionTranslationService': translation.CollectionTranslationService,
        'TranslationConfigurationError': translation.TranslationConfigurationError,
        'TranslationFailure': translation.TranslationFailure,
        'logger': logging.getLogger(__name__),
        'CollectionPersistenceService': e.persistence.CollectionPersistenceService,
        'IntegrityError': IntegrityError,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(module_path), 'exec'), scope)
    assert await scope['_process_and_save'](e.db, object(), NOW) == expected
    assert sum(call[1]['request_id'].startswith('collection-processing:') for call in e.state.category_requests) == 1
    articles = e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert len(articles) == int(expected == 'inserted')
    if articles:
        assert articles[0].summary == '研究机构开展管道检测试验。'
