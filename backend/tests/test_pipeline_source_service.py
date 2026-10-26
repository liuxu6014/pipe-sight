"""Source administration against the approved thirteen-field source schema."""

import asyncio
from datetime import timedelta

import pytest
from intelligence import test_collection_rollout as collection_support
from intelligence.test_collection_rollout import NOW, AsyncMemorySession, enqueue, execute, source

env = collection_support.env


@pytest.mark.asyncio
async def test_save_source_persists_new_contract_and_returns_stable_camelcase_ids(env):
    e = env
    s = await source(e, name='新增来源', cron='0 */4 * * *')
    assert s['sourceId'] == s['id'] == s['source_code']
    assert s['isEnabled'] and s['nextRunAt'] and s['timezone'] == 'Asia/Shanghai'
    row = await e.repo.source(e.db, s['id'])
    assert row.adapter == 'fixed' and row.type == 'website' and row.config == {}
    assert not hasattr(row, 'last_status') and not hasattr(row, 'owner_id')


@pytest.mark.parametrize(
    'overrides',
    [
        {'adapter': 'unknown'},
        {'cron': 'every six hours'},
        {'timezone': 'not/a-zone'},
        {'type': 'paper', 'adapter': 'pipechina_group_news'},
        {'url': 'http://127.0.0.1/private'},
    ],
)
@pytest.mark.asyncio
async def test_save_source_rejects_invalid_configuration(env, overrides):
    with pytest.raises(env.collection.ConfigurationError):
        await source(env, **overrides)


@pytest.mark.asyncio
async def test_update_source_rejects_missing_source(env):
    with pytest.raises(env.conflict, match='数据源不存在'):
        await source(env, source_id='999999')


@pytest.mark.asyncio
async def test_source_type_is_immutable_but_rules_can_change_without_changing_run_snapshot(env):
    e = env
    s = await source(e, config={'revision': 'old'})
    r = await enqueue(e, s['id'])
    with pytest.raises(e.conflict):
        await source(e, source_id=int(s['id']), type='paper')
    await source(e, source_id=int(s['id']), config={'revision': 'new'})
    run = await e.repo.run(e.db, r['id'])
    assert run.config_snapshot['config'] == {'revision': 'old'}


@pytest.mark.asyncio
async def test_disable_cancels_queue_and_enable_recalculates_cursor_without_reviving(env):
    e = env
    s = await source(e, cron='0 8 * * *')
    r = await enqueue(e, s['id'])
    disabled = await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert disabled['isEnabled'] is False and disabled['nextRunAt'] is None
    assert (await e.repo.run(e.db, r['id'])).status == 'cancelled'
    enabled = await e.service.set_enabled(
        e.db, s['id'], True, registry=e.registry, clock=lambda: NOW + timedelta(days=1)
    )
    assert enabled['isEnabled'] and enabled['nextRunAt']
    assert (await execute(e, r['id']))['status'] == 'skipped'


@pytest.mark.asyncio
async def test_disabling_running_source_requires_separate_stop_request(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=60)
    await e.service.set_enabled(e.db, s['id'], False, registry=e.registry, clock=e.clock)
    assert (await e.repo.run(e.db, r['id'])).status == 'running'
    stopped = await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    assert stopped['status'] == 'stopping' and stopped['finishedAt'] is None


@pytest.mark.asyncio
async def test_manual_collection_is_persisted_without_running_adapter_in_api(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    assert r['status'] == 'queued' and not e.state.calls
    assert (await enqueue(e, s['id'], 'manual:duplicate'))['id'] == r['id']


@pytest.mark.asyncio
async def test_disable_and_admission_from_two_sessions_cannot_leave_startable_task(env):
    e = env
    s = await source(e)

    async def admission():
        async with AsyncMemorySession(e.engine) as db:
            return await e.service.queue_collection_run(
                db, s['id'], request_id='manual:race', registry=e.registry, clock=e.clock
            )

    async def disable():
        async with AsyncMemorySession(e.engine) as db:
            return await e.service.set_enabled(db, s['id'], False, registry=e.registry, clock=e.clock)

    admitted, disabled = await asyncio.gather(admission(), disable())
    assert disabled['isEnabled'] is False
    run = await e.repo.run(e.db, admitted['id'])
    assert run.status == 'cancelled' and run.finished_at and run.stop_requested_at
    assert await e.repo.claim(e.db, run.id, now=NOW, lease_seconds=60) is None


@pytest.mark.asyncio
async def test_retry_new_record_preserves_failed_parent_and_counts(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    e.state.batches = [e.collection.TransientCollectionError()]
    await execute(e, r['id'])
    child = await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    assert child['parentId'] == r['id'] and child['status'] == 'queued'
    assert child['fetchedCount'] == child['savedCount'] == child['failedCount'] == 0
    assert (await e.repo.run(e.db, r['id'])).status == 'failed'


@pytest.mark.asyncio
async def test_successful_or_cancelled_runs_are_not_retry_parents(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    await execute(e, r['id'])
    with pytest.raises(e.conflict):
        await e.service.retry_collection_run(e.db, r['id'], registry=e.registry, clock=e.clock)
    queued = await enqueue(e, s['id'], 'manual:cancel')
    await e.service.stop_collection_run(e.db, queued['id'], clock=e.clock)
    with pytest.raises(e.conflict):
        await e.service.retry_collection_run(e.db, queued['id'], registry=e.registry, clock=e.clock)


@pytest.mark.asyncio
async def test_task_list_explains_source_state_and_latest_run_without_review_dependencies(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    task = (await e.service.list_collection_tasks(e.db))['rows'][0]
    assert task['status'] == 'cancelled' and task['latestRunId'] == r['id']
    assert task['sourceId'] == s['id'] and task['isEnabled']
    assert 'cancelled' in task['latestMessage']
