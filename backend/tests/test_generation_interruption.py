"""An unknown provider result requires explicit retry instead of a second paid call."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from test_research_model_generation import execution_context
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import queue, seed

env = memory_env
db = memory_db
no_external_network = offline_network


@pytest.mark.asyncio
async def test_expired_running_attempt_is_not_automatically_claimed_again(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.claim_research_job(db, result['jobId'], 7)
    token = job.execution_token
    job.lease_expires_at = env.models.utcnow() - timedelta(seconds=1)
    await db.commit()

    assert await env.repo.ResearchDao.claim_research_job(db, job.id, 7) is None
    assert job.status == 'failed' and job.attempts == 1
    assert '未自动重发' in job.error
    assert job.execution_token is None and job.lease_expires_at is None and job.finished_at
    assert await env.repo.ResearchDao.lock_running_research_job(db, job.id, 7, token) is None
    assert (await env.repo.ResearchDao.get_report(db, result['reportId'], 7)).content == ''
    retried = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=job.id)
    assert retried['jobId'] != result['jobId'] and retried['status'] == 'queued'


@pytest.mark.asyncio
@pytest.mark.parametrize('cancelled_by_user', [False, True])
async def test_worker_shutdown_settles_unknown_run_without_overwriting_user_cancel(
    env, db, monkeypatch, cancelled_by_user
):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    execution, factory = execution_context(env, db, monkeypatch)
    started = asyncio.Event()

    async def provider(*_args, **_kwargs):
        started.set()
        await asyncio.Event().wait()

    generate = AsyncMock(side_effect=provider)
    monkeypatch.setattr(execution.ResearchModelGenerationService, 'generate_content', generate)
    task = asyncio.create_task(execution.ResearchExecutionService.process(job_id=result['jobId'], user_id=7))
    await asyncio.wait_for(started.wait(), timeout=2)
    if cancelled_by_user:
        async with factory() as cancel_db:
            await env.app.ResearchApplicationService.cancel_job(cancel_db, 7, result['jobId'])
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    db.s.expire_all()
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    assert job.status == ('cancelled' if cancelled_by_user else 'failed')
    assert job.attempts == 1 and job.execution_token is None and job.lease_expires_at is None
    assert (await env.repo.ResearchDao.get_report(db, result['reportId'], 7)).content == ''
    generate.assert_awaited_once()
