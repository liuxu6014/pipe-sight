"""Persistent collection admission, fencing and retry-chain integrity."""

import asyncio
from datetime import timedelta

import pytest
from intelligence import test_collection_rollout as collection_support
from intelligence.test_collection_rollout import NOW, AsyncMemorySession, enqueue, source

env = collection_support.env
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_ready_queue_keeps_disabled_sources_for_terminal_cleanup(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    current = await e.repo.source(e.db, s['id'])
    current.is_enabled = False
    await e.db.commit()
    assert await e.repo.ready(e.db, NOW) == [int(r['id'])]
    assert await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=30) is None
    assert (await e.repo.run(e.db, r['id'])).status == 'cancelled'


@pytest.mark.asyncio
async def test_queued_stop_is_immediate_and_never_claimed(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    stopped = await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    assert stopped['status'] == 'cancelled' and stopped['startedAt'] is None and stopped['finishedAt']
    assert await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=30) is None


@pytest.mark.asyncio
async def test_running_stop_fences_new_batches_until_executor_confirms(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=30)
    token = run.execution_token
    stopped = await e.service.stop_collection_run(e.db, r['id'], clock=e.clock)
    assert stopped['status'] == 'stopping' and stopped['finishedAt'] is None
    assert (await enqueue(e, s['id'], 'manual:concurrent'))['id'] == r['id']
    with pytest.raises(e.lost):
        await e.persistence.CollectionPersistenceService.save_batch(
            e.db,
            r['id'],
            token,
            [{'title': '不能写入', 'url': 'https://example.test/stop'}],
            {},
            now=NOW,
            clock=e.clock,
        )
    assert not e.db.sync.scalars(select(e.content.PipelineArticle)).all()
    assert (await e.repo.finish(e.db, r['id'], token, now=NOW)).status == 'cancelled'


@pytest.mark.asyncio
async def test_database_partial_unique_index_rejects_second_active_source(env):
    e = env
    s = await source(e)
    await enqueue(e, s['id'])
    e.db.add(
        e.models.PipelineCrawlRun(
            id=900004,
            source_id=int(s['id']),
            trigger_type='manual',
            request_id='manual:second',
            available_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        await e.db.commit()
    await e.db.rollback()
    stmt = select(e.models.PipelineSource).where(e.models.PipelineSource.id == int(s['id'])).with_for_update()
    assert 'FOR UPDATE' in str(stmt.compile(dialect=postgresql.dialect()))


@pytest.mark.asyncio
async def test_concurrent_retry_clicks_have_one_child_and_parent_remains_failed(env):
    e = env
    s = await source(e, config={'retry': {'backoff_seconds': 10}})
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=30)
    await e.repo.finish(e.db, r['id'], run.execution_token, now=NOW, error='临时采集故障或请求超时')

    async def submit(request_id):
        async with AsyncMemorySession(e.engine) as db:
            return await e.service.retry_collection_run(
                db, r['id'], request_id=request_id, registry=e.registry, clock=e.clock
            )

    left, right = await asyncio.gather(submit('retry:left'), submit('retry:right'))
    assert left['id'] == right['id'] and left['parentId'] == r['id']
    child = await e.repo.run(e.db, left['id'])
    assert e.sources.aware(child.available_at) == NOW + timedelta(seconds=10)
    parent = await e.repo.run(e.db, r['id'])
    assert parent.status == 'failed' and parent.error and parent.finished_at
    assert len(await e.repo.history(e.db)) == 2


@pytest.mark.asyncio
async def test_expired_token_cannot_finish_or_write_after_recovery(env):
    e = env
    s = await source(e)
    r = await enqueue(e, s['id'])
    run = await e.repo.claim(e.db, r['id'], now=NOW, lease_seconds=5)
    token = run.execution_token
    await e.repo.recover(e.db, r['id'], now=NOW + timedelta(seconds=6))
    with pytest.raises(e.lost):
        await e.repo.finish(e.db, r['id'], token, now=NOW + timedelta(seconds=7))
    with pytest.raises(e.lost):
        await e.repo.heartbeat(e.db, r['id'], token, now=NOW + timedelta(seconds=7), lease_seconds=30)
