"""Offline translation contract: real collection state machine, mocked provider."""

import asyncio
import importlib
import json
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

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
    e.db.add(e.config(key='pipeline.translation.modelId', value='1'))
    await e.db.commit()
    return await source(e, model_id=None, type=kind), model


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


def translation_calls(e):
    return [
        call
        for call in e.state.category_requests
        if call[1].get('request_id', '').startswith('collection-translation:')
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'field,translated', [('title', '管道检测技术研究'), ('abstract', '管道检测研究。\n\n这是第二段。')]
)
async def test_manual_paper_translation_is_saved_and_survives_recrawl(env, translation, field, translated) -> None:
    e = env
    source_data, _ = await configured_source(e, kind='paper')
    paper_source = SimpleNamespace(id=int(source_data['id']), type='paper')
    original = record('paper')
    await e.persistence.CollectionPersistenceService.save_record(e.db, paper_source, original, NOW)
    await e.db.commit()
    paper = e.db.sync.scalars(select(e.content.PipelinePaper)).one()
    target = f'{field}_zh'
    e.state.category_reply = json.dumps({target: translated})
    translate = getattr(translation, f'translate_paper_{field}')

    assert await translate(e.db, paper.id) == translated
    assert await translate(e.db, paper.id) == translated
    ((_, call),) = e.state.category_requests
    assert json.loads(call['prompt']) == {'text': original[field]}
    assert call['request_id'].startswith(f'paper-{field}-translation:')

    await e.persistence.CollectionPersistenceService.save_record(e.db, paper_source, original, NOW)
    await e.db.commit()
    assert getattr(paper, target) == translated
    assert paper.title == original['title']
    assert paper.abstract == original['abstract']
    assert getattr(paper, 'abstract_zh' if field == 'title' else 'title_zh') is None

    await e.persistence.CollectionPersistenceService.save_record(
        e.db, paper_source, {**original, field: 'Corrected original text'}, NOW
    )
    await e.db.commit()
    assert getattr(paper, target) is None


@pytest.mark.asyncio
async def test_manual_paper_title_translation_requires_a_configured_model(env, translation) -> None:
    from exceptions.exception import ServiceException

    e = env
    paper_source = SimpleNamespace(id=int((await source(e, type='paper'))['id']), type='paper')
    await e.persistence.CollectionPersistenceService.save_record(e.db, paper_source, record('paper'), NOW)
    await e.db.commit()
    paper = e.db.sync.scalars(select(e.content.PipelinePaper)).one()

    with pytest.raises(ServiceException) as error:
        await translation.translate_paper_title(e.db, paper.id)
    assert '选择翻译模型' in error.value.message
    assert paper.title_zh is None and not e.state.category_requests


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['title', 'abstract'])
async def test_concurrent_first_translation_shares_the_saved_result(env, translation, monkeypatch, field):
    e = env
    source_data, _ = await configured_source(e, kind='paper')
    await e.persistence.CollectionPersistenceService.save_record(
        e.db, SimpleNamespace(id=int(source_data['id']), type='paper'), record('paper'), NOW
    )
    await e.db.commit()
    paper = e.db.sync.scalars(select(e.content.PipelinePaper)).one()
    identity = paper.id
    await e.db.commit()
    reached, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def gateway(db, snapshot, **kwargs):
        calls.append(kwargs['request_id'])
        reached.set()
        await release.wait()
        return json.dumps({f'{field}_zh': '管道检测的中文译文。'})

    monkeypatch.setattr(importlib.import_module('app.research.services.model_generation').ModelGateway, 'call', gateway)

    async def request():
        async with AsyncMemorySession(e.engine) as db:
            return await translation._translate_paper_field(db, identity, field=field)

    first = asyncio.create_task(request())
    await asyncio.wait_for(reached.wait(), timeout=2)
    second = asyncio.create_task(request())
    await asyncio.sleep(0)
    assert len(calls) == 1
    release.set()
    assert await asyncio.gather(first, second) == ['管道检测的中文译文。'] * 2
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_failed_translation_releases_single_flight_for_retry(env, translation, monkeypatch):
    from exceptions.exception import ServiceException

    e = env
    source_data, _ = await configured_source(e, kind='paper')
    await e.persistence.CollectionPersistenceService.save_record(
        e.db, SimpleNamespace(id=int(source_data['id']), type='paper'), record('paper'), NOW
    )
    await e.db.commit()
    paper = e.db.sync.scalars(select(e.content.PipelinePaper)).one()
    e.state.category_reply = RuntimeError('provider unavailable')
    with pytest.raises(ServiceException):
        await translation.translate_paper_title(e.db, paper.id)
    e.state.category_reply = '{"title_zh":"重试成功的中文标题"}'
    assert await translation.translate_paper_title(e.db, paper.id) == '重试成功的中文标题'
    assert len(e.state.category_requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_at', ['acquire', 'cleanup'])
async def test_pg_translation_releases_auth_read_connection_and_finishes_unlock_before_pool_return(
    env, translation, monkeypatch, cancel_at
):
    events = []
    cleanup_started, release_cleanup = asyncio.Event(), asyncio.Event()

    class Connection:
        async def __aenter__(self):
            events.append('connect')
            return self

        async def __aexit__(self, *args):
            assert 'unlock-complete' in events
            events.append('pool-return')

        async def execute(self, statement, params):
            if 'try_advisory_lock' in str(statement):
                if cancel_at == 'acquire':
                    raise asyncio.CancelledError
                return SimpleNamespace(scalar=lambda: True)
            events.append('unlock-start')
            cleanup_started.set()
            if cancel_at == 'cleanup':
                await release_cleanup.wait()
            events.append('unlock-complete')
            return None

        async def commit(self):
            pass

        async def rollback(self):
            pass

        async def invalidate(self):
            events.append('invalidated')

    async def commit_read():
        events.append('read-commit')

    async def dispose():
        events.append('dispose')

    lock_engine = SimpleNamespace(connect=Connection, dispose=dispose)
    monkeypatch.setattr(translation, 'create_async_engine', lambda *args, **kwargs: lock_engine)
    db = SimpleNamespace(
        bind=SimpleNamespace(dialect=SimpleNamespace(name='postgresql'), url='postgresql+asyncpg://offline'),
        commit=commit_read,
    )

    async def request():
        async with translation._paper_translation_guard(db, 401, 'title'):
            pass

    task = asyncio.create_task(request())
    if cancel_at == 'cleanup':
        # A broken precondition must fail this regression rather than leave the
        # full suite waiting indefinitely on an unreachable fake barrier.
        await asyncio.wait_for(cleanup_started.wait(), timeout=2)
        task.cancel()
        await asyncio.sleep(0)
        assert 'pool-return' not in events
        release_cleanup.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=2)
    assert events.index('read-commit') < events.index('connect')
    assert events.index('unlock-complete') < events.index('pool-return')


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['website', 'wechat', 'paper'])
async def test_no_translation_model_leaves_originals_and_never_calls_provider(env, translation, kind) -> None:
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
async def test_translates_only_body_or_abstract_with_frozen_model_and_preserved_metadata(
    env, translation, kind
) -> None:
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
async def test_existing_translations_and_chinese_originals_are_not_replaced(env, translation, body, existing) -> None:
    e = env
    s, _ = await configured_source(e)
    item = {**record(), 'content': body, 'content_zh': existing}
    e.state.batches = [e.batch([item], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    assert not translation_calls(e)
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
async def test_invalid_model_rejected_before_enqueue_or_provider(env, translation, override) -> None:
    e = env
    s, _ = await configured_source(e, **override)
    with pytest.raises(e.collection.ConfigurationError):
        await enqueue(e, s['id'])
    assert not e.state.category_requests
    assert not await e.repo.history(e.db)


@pytest.mark.asyncio
async def test_model_identity_change_after_enqueue_never_calls_provider(env, translation) -> None:
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
async def test_invalid_output_fails_truthfully_and_retry_preserves_snapshot(env, translation, reply) -> None:
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
async def test_input_bound_fails_before_any_paid_call_without_truncating_original(env, translation) -> None:
    e = env
    s, _ = await configured_source(e)
    item = {**record(), 'content': 'English ' * (translation.MAX_INPUT_CHARS // 8 + 1)}
    original = deepcopy(item)
    e.state.batches = [e.batch([item], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'failed'
    assert not e.state.category_requests and item == original


@pytest.mark.asyncio
async def test_provider_failure_is_safe_failed_run_with_retry_not_fake_translation(env, translation) -> None:
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
async def test_provider_timeout_is_bounded_and_cleans_cancelled_call(env, translation, monkeypatch) -> None:
    e = env
    s, _ = await configured_source(e)
    closed = []

    async def blocked(db) -> None:
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
async def test_stop_during_translation_acknowledges_provider_cleanup_before_cancelled(env, translation) -> None:
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    closed = []

    async def stopped(db) -> None:
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
async def test_translation_return_after_lease_expiry_cannot_write_content(env, translation) -> None:
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    current = [NOW]

    async def expired(db) -> str:
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
async def test_schedule_freezes_model_and_manual_replay_does_not_revalidate_active_snapshot(env, translation) -> None:
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
async def test_later_source_model_change_does_not_change_queued_run(env, translation) -> None:
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
) -> None:
    e = env
    monkeypatch.setattr(e.processing, 'freeze', e.real_processing_freeze)
    monkeypatch.setattr(e.processing, 'prepare', e.real_processing_prepare)
    s, _ = await configured_source(e)
    e.db.add(
        e.content.PipelineCategory(
            id=801, name='分类', prompt='管理员规则', model_id=1, applies_to='news', is_enabled=True, sort_order=0
        )
    )
    await e.db.commit()
    e.db.add(e.config(key='pipeline.processing.modelId', value='1'))
    await e.db.commit()
    prompts = []

    async def gateway(db, snapshot, **kwargs) -> str:
        prompts.append(kwargs['system_prompt'])
        if kwargs['system_prompt'].startswith('你是忠实的'):
            return '{"content_zh":"中文译文供分类使用。"}'
        assert '中文译文供分类使用。' in kwargs['prompt']
        return json.dumps(
            {
                'filter': {'decision': 'keep'},
                'category_id': '801',
                'category_name': '分类',
                'summary': '译文供分类使用。',
                'entities': [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(importlib.import_module('app.research.services.model_generation').ModelGateway, 'call', gateway)
    e.state.batches = [e.batch([record()], {})]
    r = await enqueue(e, s['id'])
    assert (await execute(e, r['id']))['status'] == 'success'
    assert sum(prompt.startswith('你是忠实的') for prompt in prompts) == 1
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().category_id == 801


@pytest.mark.asyncio
async def test_legacy_run_without_model_snapshot_is_not_silently_backfilled(env, translation) -> None:
    e = env
    s, _ = await configured_source(e)
    await source(e, source_id=s['id'], model_id=1)
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
async def test_recrawl_reuses_existing_translation_for_unchanged_original(env, translation, keep_model) -> None:
    e = env
    s, _ = await configured_source(e)
    e.state.category_reply = '{"content_zh":"已有可信译文，不应覆盖。"}'
    e.state.batches = [e.batch([record()], {})]
    first = await enqueue(e, s['id'])
    assert (await execute(e, first['id']))['status'] == 'success'
    if not keep_model:
        await source(e, source_id=s['id'], model_id=None)
        setting = e.db.sync.scalars(select(e.config)).one()
        setting.value = ''
        await e.db.commit()
    second = await enqueue(e, s['id'], 'recrawl')
    assert (await execute(e, second['id']))['status'] == 'success'
    assert len(translation_calls(e)) == 1
    assert e.db.sync.scalars(select(e.content.PipelineArticle)).one().content_zh == '已有可信译文，不应覆盖。'


@pytest.mark.asyncio
async def test_effective_model_timeout_and_output_limits_are_frozen_before_call(env, translation) -> None:
    e = env
    s, _ = await configured_source(
        e, parameters={'timeout_seconds': 120, 'max_tokens': 32768, 'max_response_bytes': 32 * 1024 * 1024}
    )
    r = await enqueue(e, s['id'])
    parameters = (await e.repo.run(e.db, r['id'])).config_snapshot['translation_model']['parameters']
    assert parameters['timeout_seconds'] == 120
    assert parameters['max_tokens'] == 8192 and parameters['max_response_bytes'] == 256 * 1024


@pytest.mark.asyncio
async def test_unacknowledged_translation_cancellation_leaves_stopping_and_fences_writes(env, translation) -> None:
    e = env
    s, _ = await configured_source(e)
    r = await enqueue(e, s['id'])
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def stubborn(db) -> str | None:
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


@pytest.mark.asyncio
async def test_global_translation_settings_persist_validate_and_do_not_rewrite_source_models(env, translation) -> None:
    settings = importlib.import_module('app.intelligence.services.translation_settings')
    e = env
    assert await settings.translation_settings(e.db) == {'modelId': None}
    e.db.add(
        e.ai_model(
            id=90071992547409931,
            provider='compatible',
            code='global-text',
            base_url='https://example.test/model',
            capabilities=['text_generate'],
            parameters={},
            is_enabled=True,
        )
    )
    await e.db.commit()
    selected = await settings.save_translation_settings(e.db, '90071992547409931')
    assert selected == {'modelId': '90071992547409931'}
    s = await source(e, model_id=None)
    frozen = await e.sources.frozen_snapshot(e.db, await e.repo.source(e.db, s['id']))
    assert frozen['model_id'] is None
    assert frozen['translation_model_id'] == '90071992547409931'
    assert frozen['translation_model']['id'] == '90071992547409931'
    await settings.save_translation_settings(e.db, None)
    assert await settings.translation_settings(e.db) == {'modelId': None}
    assert len(e.db.sync.scalars(select(e.config)).all()) == 1
    assert (await e.repo.source(e.db, s['id'])).model_id is None
    await e.db.commit()
    e.state.category_reply = '{"content_zh":"统一模型提供的中文译文。"}'

    def sessions():
        return AsyncMemorySession(e.engine)

    translated = await translation.CollectionTranslationService.translate(sessions, frozen, [record()])
    assert translated[0]['content_zh'] == '统一模型提供的中文译文。'
    assert e.state.category_requests[0][0]['id'] == '90071992547409931'


@pytest.mark.asyncio
async def test_global_translation_disabled_ignores_legacy_source_binding_and_no_fallback_on_invalid_model(
    env, translation
) -> None:
    settings = importlib.import_module('app.intelligence.services.translation_settings')
    e = env
    s, model = await configured_source(e)
    await source(e, source_id=s['id'], model_id=1)
    await settings.save_translation_settings(e.db, None)
    frozen = await e.sources.frozen_snapshot(e.db, await e.repo.source(e.db, s['id']))
    assert frozen['model_id'] == 1
    assert frozen['translation_model_id'] is None and 'translation_model' not in frozen
    await e.db.commit()
    assert (
        await translation.CollectionTranslationService.translate(
            lambda: AsyncMemorySession(e.engine), frozen, [record()]
        )
    )[0].get('content_zh') is None
    assert not e.state.category_requests
    for capabilities, enabled in [(['image_generate'], True), (['text_generate'], False)]:
        model.capabilities, model.is_enabled = capabilities, enabled
        await e.db.commit()
        with pytest.raises(translation.TranslationConfigurationError):
            await settings.save_translation_settings(e.db, 1)
        assert await settings.translation_settings(e.db) == {'modelId': None}
    with pytest.raises(translation.TranslationConfigurationError):
        await settings.save_translation_settings(e.db, 99)


def test_global_translation_dto_requires_explicit_positive_id_or_null(env) -> None:
    from pydantic import ValidationError

    dto = importlib.import_module('app.intelligence.schemas.ai_model').TranslationModelSelection
    assert dto(modelId='90071992547409931').model_id == 90071992547409931
    assert dto(modelId=None).model_id is None
    for value in [{}, {'modelId': False}, {'modelId': 0}, {'modelId': 'bad'}, {'modelId': 1, 'apiKey': 'not-allowed'}]:
        with pytest.raises(ValidationError):
            dto(**value)
