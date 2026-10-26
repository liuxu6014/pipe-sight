"""Offline translation contract: real collection state machine, mocked provider."""

import asyncio
import importlib
import json
from copy import deepcopy
from datetime import timedelta

import pytest
import test_collection_rollout as support
from sqlalchemy import select
from test_collection_rollout import NOW, AsyncMemorySession, enqueue, execute, source

env = support.env


@pytest.fixture
def translation(env, monkeypatch):
    gateway = importlib.import_module('app.research.services.model_generation').ModelGateway
    monkeypatch.setattr(gateway, 'supported_providers', frozenset({'compatible'}), raising=False)
    return importlib.import_module('app.intelligence.services.collection_translation')


async def configured_source(e, *, kind='website', **overrides):
    model = e.ai_model(
        id=1,
        provider='compatible',
        code='text-one',
        base_url='https://example.test/model',
        capabilities=['text_generate'],
        parameters={'timeout_seconds': 30, 'max_tokens': 2048},
        is_enabled=True,
    )
    model.credential_ref = 'env:OFFLINE_TRANSLATION_ONLY'
    for key, value in overrides.items():
        setattr(model, key, value)
    e.db.add(model)
    await e.db.commit()
    return await source(e, model_id=1, type=kind), model


def record(kind='website'):
    return {
        'title': 'Original title',
        'url': 'https://example.test/translation',
        'author': 'Original author',
        'published_at': NOW.isoformat(),
        **(
            {
                'doi': '10.1234/offline',
                'abstract': 'An English abstract about pipeline inspection.',
                'authors': 'Original authors',
                'published_date': '2024-06',
                'content': 'PAPER FULLTEXT MUST NEVER BE SENT',
            }
            if kind == 'paper'
            else {'content': 'An English article about pipeline inspection.'}
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['website', 'wechat', 'paper'])
async def test_no_translation_model_leaves_originals_and_never_calls_provider(env, translation, kind):
    e = env
    s = await source(e, type=kind)
    original = record(kind)
    e.state.batches = [e.batch([original], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    assert not e.state.category_requests
    model = e.content.PipelinePaper if kind == 'paper' else e.content.PipelineArticle
    saved = e.db.sync.scalars(select(model)).one()
    field = 'abstract' if kind == 'paper' else 'content'
    assert getattr(saved, field) == original[field] and getattr(saved, field + '_zh') is None


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['website', 'wechat', 'paper'])
async def test_translates_only_body_or_abstract_with_frozen_model_and_preserved_metadata(env, translation, kind):
    e = env
    s, model = await configured_source(e, kind=kind)
    original = record(kind)
    before = deepcopy(original)
    field = 'abstract_zh' if kind == 'paper' else 'content_zh'
    e.state.category_reply = json.dumps({field: '这是忠实的中文译文。'}, ensure_ascii=False)
    e.state.batches = [e.batch([original], {})]
    r = await enqueue(e, s['id'])
    run = await e.repo.run(e.db, r['id'])
    frozen = deepcopy(run.config_snapshot)
    assert frozen['translation_model']['id'] == '1'
    assert 'credential' not in json.dumps(frozen).lower() and 'OFFLINE_TRANSLATION_ONLY' not in json.dumps(frozen)
    model.parameters = {'timeout_seconds': 10, 'max_tokens': 1}
    await e.db.commit()
    assert (await execute(e, r['id']))['status'] == 'success'
    saved_model = e.content.PipelinePaper if kind == 'paper' else e.content.PipelineArticle
    saved = e.db.sync.scalars(select(saved_model)).one()
    assert getattr(saved, field) == '这是忠实的中文译文。'
    assert saved.title == original['title'] and saved.url == original['url']
    assert (
        getattr(saved, 'abstract' if kind == 'paper' else 'content')
        == original['abstract' if kind == 'paper' else 'content']
    )
    if kind == 'paper':
        assert saved.authors == original['authors'] and saved.published_date == '2024-06'
        assert not hasattr(saved, 'content')
    else:
        assert saved.author == original['author'] and saved.published_at.replace(tzinfo=NOW.tzinfo) == NOW
    assert original == before
    assert (await e.repo.run(e.db, r['id'])).config_snapshot == frozen
    captured, call = e.state.category_requests[0]
    assert captured['parameters']['max_tokens'] == 2048
    assert call['capability'] == 'text_generate' and call.get('task_id') is None
    assert 'PAPER FULLTEXT' not in call['prompt'] and call['request_id'].startswith('collection-translation:')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'body,existing',
    [('Already translated body', '已有译文'), ('Already translated body', ''), ('这是中文原文。', None)],
)
async def test_existing_translations_and_chinese_originals_are_not_replaced(env, translation, body, existing):
    e = env
    s, _ = await configured_source(e)
    item = {**record(), 'content': body, 'content_zh': existing}
    e.state.batches = [e.batch([item], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    assert not e.state.category_requests
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().content_zh == existing


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'override',
    [
        {'is_enabled': False},
        {'capabilities': ['image_generate']},
        {'provider': 'unsupported-native'},
        {'parameters': {'api_key': 'MUST_NOT_FREEZE'}},
    ],
)
async def test_invalid_model_rejected_before_enqueue_or_provider(env, translation, override):
    e = env
    s, _ = await configured_source(e, **override)
    with pytest.raises(e.collection.ConfigurationError):
        await enqueue(e, s['id'])
    assert not e.state.category_requests
    assert not await e.repo.history(e.db)


@pytest.mark.asyncio
async def test_model_identity_change_after_enqueue_never_calls_provider(env, translation):
    e = env
    s, model = await configured_source(e)
    r = await enqueue(e, s['id'])
    model.code = 'different-model'
    await e.db.commit()
    e.state.batches = [e.batch([record()], {})]
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert not e.state.category_requests
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'reply',
    [
        'not-json',
        '{"content_zh":"中文一","content_zh":"中文二"}',
        '{"content_zh":""}',
        '{"content_zh":123}',
        '{"content_zh":"English unchanged"}',
        '{"content_zh":"中文","title":"changed"}',
    ],
)
async def test_invalid_output_fails_truthfully_and_retry_preserves_snapshot(env, translation, reply):
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    frozen = deepcopy((await e.repo.run(e.db, r['id'])).config_snapshot)
    e.state.batches = [e.batch([record()], {})]
    e.state.category_reply = reply
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    child = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert (await e.repo.run(e.db, child['id'])).config_snapshot == frozen
    assert (await e.repo.run(e.db, r['id'])).status == 'failed'
    e.state.category_reply = '{"content_zh":"正确译文。"}'
    result = await e.collection.PipelineCollectionService.execute(
        e.db, child['id'], registry=e.registry, clock=lambda: NOW + timedelta(seconds=31)
    )
    assert result['status'] == 'success'
    assert e.state.category_requests[0][1]['request_id'] == e.state.category_requests[1][1]['request_id']


@pytest.mark.asyncio
async def test_input_bound_fails_before_any_paid_call_without_truncating_original(env, translation):
    e = env
    s, _ = await configured_source(e)
    item = {**record(), 'content': 'English ' * (translation.MAX_INPUT_CHARS // 8 + 1)}
    original = deepcopy(item)
    e.state.batches = [e.batch([item], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert not e.state.category_requests and item == original


@pytest.mark.asyncio
async def test_provider_failure_is_safe_failed_run_with_retry_not_fake_translation(env, translation):
    e = env
    s, _ = await configured_source(e)
    e.state.batches = [e.batch([record()], {})]
    e.state.category_reply = RuntimeError('SECRET provider response')
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'failed'
    failed = await e.repo.run(e.db, r['id'])
    assert 'SECRET' not in failed.error and failed.saved_count == 0
    assert (await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock))['parentId'] == r[
        'id'
    ]


@pytest.mark.asyncio
async def test_provider_timeout_is_bounded_and_cleans_cancelled_call(env, translation, monkeypatch):
    e = env
    s, _ = await configured_source(e)
    closed = []

    async def blocked(db):
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    e.state.category_reply = blocked
    e.state.batches = [e.batch([record()], {})]
    r = await enqueue(e, s['id'])
    monkeypatch.setattr(translation, 'MAX_CALL_TIMEOUT_SECONDS', 0.01)
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert closed and e.state.cleanup


@pytest.mark.asyncio
async def test_stop_during_translation_acknowledges_provider_cleanup_before_cancelled(env, translation):
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    closed = []

    async def stopped(db):
        async with AsyncMemorySession(e.engine) as control:
            result = await e.service.stop_collection_run(control, r['id'], clock=e.clock)
            assert result['status'] == 'stopping' and result['finishedAt'] is None
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(True)

    e.state.category_reply = stopped
    e.state.batches = [e.batch([record()], {})]
    result = await e.collection.PipelineCollectionService.execute(
        e.db, r['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.005
    )
    assert result['status'] == 'cancelled' and closed and e.state.cleanup
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert (await e.repo.run(e.db, r['id'])).saved_count == 0


@pytest.mark.asyncio
async def test_translation_return_after_lease_expiry_cannot_write_content(env, translation):
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    current = [NOW]

    async def expired(db):
        current[0] += timedelta(seconds=10)
        return '{"content_zh":"过期执行器不能写入。"}'

    e.state.category_reply = expired
    e.state.batches = [e.batch([record()], {})]
    result = await e.collection.PipelineCollectionService.execute(
        e.db, r['id'], registry=e.registry, clock=lambda: current[0], lease_seconds=5, pulse_seconds=0.005
    )
    assert result['status'] == 'fenced'
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()


@pytest.mark.asyncio
async def test_schedule_freezes_model_and_manual_replay_does_not_revalidate_active_snapshot(env, translation):
    e = env
    s, model = await configured_source(e)
    s = await source(e, source_id=s['id'], model_id=1, cron='0 8 * * *')
    row = await e.repo.source(e.db, s['id'])
    row.next_run_at = NOW
    await e.db.commit()
    scheduled = await e.service.schedule_due_source(e.db, s['id'], registry=e.registry, clock=e.clock)
    frozen = deepcopy((await e.repo.run(e.db, scheduled['id'])).config_snapshot)
    assert frozen['translation_model']['id'] == '1'
    model.is_enabled = False
    await e.db.commit()
    assert (await enqueue(e, s['id'], request_id='another-request'))['id'] == scheduled['id']
    assert (await e.repo.run(e.db, scheduled['id'])).config_snapshot == frozen


@pytest.mark.asyncio
async def test_later_source_model_change_does_not_change_queued_run(env, translation):
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    e.db.add(
        e.ai_model(
            id=2,
            provider='compatible',
            code='second',
            base_url='https://example.test/second',
            capabilities=['text_generate'],
            parameters={},
            is_enabled=True,
        )
    )
    await e.db.commit()
    await source(e, source_id=s['id'], model_id=2)
    e.state.category_reply = '{"content_zh":"仍然使用冻结的原模型。"}'
    e.state.batches = [e.batch([record()], {})]
    assert (await execute(e, r['id']))['status'] == 'success'
    assert e.state.category_requests[0][0]['id'] == '1'


@pytest.mark.asyncio
async def test_category_classification_consumes_translation_and_still_sets_single_category(
    env, translation, monkeypatch
):
    e = env
    s, _ = await configured_source(e)
    e.db.add(
        e.content.PipelineCategory(
            id=801, name='分类', prompt='管理员规则', model_id=1, applies_to='news', is_enabled=True, sort_order=0
        )
    )
    await e.db.commit()
    prompts = []

    async def gateway(db, snapshot, **kwargs):
        prompts.append(kwargs['prompt'])
        if kwargs['system_prompt'].startswith('你是忠实的'):
            return '{"content_zh":"中文译文供分类使用。"}'
        assert '中文译文供分类使用。' in kwargs['prompt']
        return '{"match":true}'

    monkeypatch.setattr(importlib.import_module('app.research.services.model_generation').ModelGateway, 'call', gateway)
    e.state.batches = [e.batch([record()], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    assert len(prompts) == 2
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().category_id == 801


@pytest.mark.asyncio
async def test_legacy_run_without_model_snapshot_is_not_silently_backfilled(env, translation):
    e = env
    s, _ = await configured_source(e)
    r = await e.repo.enqueue(
        e.db,
        int(s['id']),
        request_id='legacy-run',
        now=NOW,
        snapshot=e.sources.snapshot(await e.repo.source(e.db, s['id'])),
    )
    original_snapshot = deepcopy(r.config_snapshot)
    e.state.batches = [e.batch([record()], {})]
    assert (await execute(e, str(r.id)))['status'] == 'failed'
    assert not e.state.category_requests
    assert (await e.repo.run(e.db, r.id)).config_snapshot == original_snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize('keep_model', [True, False])
async def test_recrawl_reuses_existing_translation_for_unchanged_original(env, translation, keep_model):
    e = env
    s, _ = await configured_source(e)
    e.state.category_reply = '{"content_zh":"已有可信译文，不应覆盖。"}'
    e.state.batches = [e.batch([record()], {})]
    first = await enqueue(e, s['id'])
    assert (await execute(e, first['id']))['status'] == 'success'
    if not keep_model:
        await source(e, source_id=s['id'], model_id=None)
    second = await enqueue(e, s['id'], 'recrawl')
    assert (await execute(e, second['id']))['status'] == 'success'
    assert len(e.state.category_requests) == 1
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().content_zh == '已有可信译文，不应覆盖。'


@pytest.mark.asyncio
async def test_effective_model_timeout_and_output_limits_are_frozen_before_call(env, translation):
    e = env
    s, _ = await configured_source(
        e, parameters={'timeout_seconds': 120, 'max_tokens': 32768, 'max_response_bytes': 32 * 1024 * 1024}
    )
    r = await enqueue(e, s['id'])
    parameters = (await e.repo.run(e.db, r['id'])).config_snapshot['translation_model']['parameters']
    assert parameters['timeout_seconds'] == 60
    assert parameters['max_tokens'] == 8192 and parameters['max_response_bytes'] == 256 * 1024


@pytest.mark.asyncio
async def test_unacknowledged_translation_cancellation_leaves_stopping_and_fences_writes(env, translation):
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stubborn(db):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await release.wait()
            return '{"content_zh":"迟到的输出不可写入。"}'
        finally:
            finished.set()

    e.state.category_reply = stubborn
    e.state.batches = [e.batch([record()], {})]
    task = asyncio.create_task(
        e.collection.PipelineCollectionService.execute(
            e.db, r['id'], registry=e.registry, clock=e.clock, pulse_seconds=0.005
        )
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        async with AsyncMemorySession(e.engine) as control:
            await e.service.stop_collection_run(control, r['id'], clock=e.clock)
        result = await asyncio.wait_for(task, timeout=1)
        assert result['status'] == 'fenced' and not finished.is_set()
        run = await e.repo.run(e.db, r['id'])
        assert run.status == 'stopping' and run.finished_at is None and run.saved_count == 0
        assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    finally:
        release.set()
        await asyncio.wait_for(finished.wait(), timeout=1)
        await asyncio.sleep(0.02)
