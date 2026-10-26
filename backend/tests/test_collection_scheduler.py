"""Collection wakeups against the new source cursor/run lease contract, offline."""

import asyncio
import importlib
from datetime import timedelta
from types import SimpleNamespace

import pytest
from intelligence import test_collection_rollout as collection_support
from intelligence.test_collection_rollout import NOW, AsyncMemorySession, enqueue, source

env = collection_support.env


class FakeScheduler:
    def __init__(self):
        self.jobs, self.removed = [], []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append({'func': func, 'trigger': trigger, **kwargs})

    def get_jobs(self):
        return [SimpleNamespace(id='_pipesight_collection_old-source'), SimpleNamespace(id='unrelated-wakeup')]

    def remove_job(self, job_id):
        self.removed.append(job_id)


@pytest.mark.asyncio
async def test_registers_generic_wakeups_without_bootstrap_or_database(env):
    scheduler_module = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    scheduler = FakeScheduler()
    result = await scheduler_module.register_real_collection_schedules(scheduler)
    assert set(result) == {
        '_pipesight_collection_scan',
        '_pipesight_collection_execute',
        '_pipesight_collection_recover',
    }
    assert len(scheduler.jobs) == 3 and all(job['trigger'] == 'interval' for job in scheduler.jobs)
    assert scheduler.removed == ['_pipesight_collection_old-source']
    assert not env.state.calls


@pytest.mark.asyncio
async def test_scheduled_cursor_enqueues_once_and_does_not_collect_in_scanner(env, monkeypatch):
    e = env
    scheduler = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    s = await source(e, cron='* * * * *', timezone='UTC')
    monkeypatch.setattr(scheduler, 'datetime', SimpleNamespace(now=lambda tz: NOW + timedelta(minutes=1)))
    original = e.service.schedule_due_source

    async def due(db, source_id, **kwargs):
        return await original(db, source_id, **kwargs, clock=lambda: NOW + timedelta(minutes=1))

    monkeypatch.setattr(e.service, 'schedule_due_source', due)
    sessions = lambda: AsyncMemorySession(e.engine)
    first = await scheduler.scan_due_sources(sessions=sessions, registry=e.registry)
    assert first[0]['status'] == 'queued' and first[0]['sourceId'] == s['id']
    assert await scheduler.scan_due_sources(sessions=sessions, registry=e.registry) == []
    assert not e.state.calls


@pytest.mark.asyncio
async def test_scheduled_round_skips_source_with_active_run_and_advances_cursor(env):
    e = env
    s = await source(e, cron='* * * * *', timezone='UTC')
    r = await enqueue(e, s['id'])
    result = await e.service.schedule_due_source(
        e.db, s['id'], registry=e.registry, clock=lambda: NOW + timedelta(minutes=5)
    )
    assert result is None
    assert [run.id for run in await e.repo.history(e.db)] == [int(r['id'])]


@pytest.mark.asyncio
async def test_worker_reentry_does_not_run_same_source_twice(env):
    e = env
    scheduler = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    s = await source(e)
    r = await enqueue(e, s['id'])
    started, release = asyncio.Event(), asyncio.Event()

    async def blocked():
        started.set()
        await release.wait()
        raise e.collection.TransientCollectionError('endpoint unavailable')

    e.state.batches = [blocked]
    sessions = lambda: AsyncMemorySession(e.engine)
    task = asyncio.create_task(scheduler.run_queued_collection(r['id'], sessions=sessions, registry=e.registry))
    await asyncio.wait_for(started.wait(), timeout=1)
    second = await scheduler.run_queued_collection(r['id'], sessions=sessions, registry=e.registry)
    assert second['status'] == 'skipped'
    release.set()
    first = await asyncio.wait_for(task, timeout=1)
    assert first['status'] == 'failed' and len(e.state.calls) == 1
    run = await e.repo.run(e.db, r['id'])
    assert run.execution_token is None and run.lease_expires_at is None


@pytest.mark.asyncio
async def test_queued_worker_respects_source_disabled_before_claim(env):
    e = env
    scheduler = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    s = await source(e)
    r = await enqueue(e, s['id'])
    # A configuration writer disabling the source before the worker acquires it.
    current = await e.repo.source(e.db, s['id'])
    current.is_enabled = False
    await e.db.commit()
    result = await scheduler.run_queued_collection(
        r['id'], sessions=lambda: AsyncMemorySession(e.engine), registry=e.registry
    )
    assert result['status'] == 'skipped'
    run = await e.repo.run(e.db, r['id'])
    assert run.status == 'cancelled' and run.started_at is None and run.stop_requested_at and run.finished_at
    assert not e.state.calls


@pytest.mark.asyncio
async def test_worker_marks_adapter_preflight_failure_terminal(env):
    e = env
    scheduler = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.run(e.db, r['id'])
    run.config_snapshot = {**run.config_snapshot, 'adapter': 'not-registered'}
    await e.db.commit()
    result = await scheduler.run_queued_collection(
        r['id'], sessions=lambda: AsyncMemorySession(e.engine), registry=e.registry
    )
    assert result['status'] == 'failed'
    run = await e.repo.run(e.db, r['id'])
    assert run.status == 'failed' and run.finished_at and run.execution_token is None
    assert '配置' in run.error


@pytest.mark.asyncio
async def test_recovery_fences_expired_execution_and_keeps_stopping_unconfirmed(env, monkeypatch):
    e = env
    scheduler = importlib.import_module('app.intelligence.tasks.collection_scheduler')
    s, s2 = await source(e), await source(e)
    running, stopping = await enqueue(e, s['id']), await enqueue(e, s2['id'], 'manual:stop')
    await e.repo.claim(e.db, running['id'], now=NOW, lease_seconds=10)
    await e.repo.claim(e.db, stopping['id'], now=NOW, lease_seconds=10)
    await e.service.stop_collection_run(e.db, stopping['id'], clock=e.clock)
    monkeypatch.setattr(scheduler, 'datetime', SimpleNamespace(now=lambda tz: NOW + timedelta(seconds=11)))
    result = await scheduler.recover_expired_collections(
        sessions=lambda: AsyncMemorySession(e.engine), registry=e.registry
    )
    assert {row['status'] for row in result} == {'failed', 'stopping'}
    run = await e.repo.run(e.db, stopping['id'])
    assert run.finished_at is None and run.execution_token is None
