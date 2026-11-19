"""Repeated retry commands reuse one durable successor, including lost responses."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import payload, queue, seed

env = memory_env
db = memory_db
no_external_network = offline_network


@pytest.fixture(autouse=True)
def file_evidence_only(env, monkeypatch):
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))


@pytest.mark.asyncio
@pytest.mark.parametrize('parent_status', ['failed', 'cancelled'])
@pytest.mark.parametrize('successor_status', ['queued', 'running', 'completed', 'failed', 'cancelled'])
async def test_retry_replay_returns_the_same_successor_without_new_generation(env, db, parent_status, successor_status):
    seed(env, db)
    submitted = await queue(env, db, payload())
    parent = await env.repo.ResearchDao.get_research_job(db, submitted['jobId'], 7)
    parent.status = parent_status
    snapshot, materials = deepcopy(parent.config_snapshot), deepcopy(parent.materials)
    await db.commit()

    first = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=parent.id)
    successor = await env.repo.ResearchDao.get_research_job(db, first['jobId'], 7)
    successor.status = successor_status
    await db.commit()
    # Fresh identity map simulates a subsequent HTTP request, not an in-page flag.
    db.s.expunge_all()
    again = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=submitted['jobId'])

    assert first['reused'] is False and again['reused'] is True
    assert again['jobId'] == first['jobId'] and again['reportId'] == submitted['reportId']
    assert again['status'] == successor_status
    assert await db.scalar(select(func.count()).select_from(env.models.PipelineResearchJob)) == 2
    assert await db.scalar(select(func.count()).select_from(env.models.PipelineReport)) == 1
    replay = await env.repo.ResearchDao.get_research_job(db, first['jobId'], 7)
    assert replay.config_snapshot == snapshot and replay.materials == materials and replay.attempts == 0


@pytest.mark.asyncio
async def test_a_failed_successor_can_be_retried_but_other_users_cannot_replay_it(env, db):
    seed(env, db)
    submitted = await queue(env, db, payload())
    parent = await env.repo.ResearchDao.get_research_job(db, submitted['jobId'], 7)
    parent.status = 'failed'
    await db.commit()
    first = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=parent.id)
    with pytest.raises(env.exc):
        await env.app.ResearchApplicationService.queue_retry(db, user_id=8, job_id=parent.id)
    successor = await env.repo.ResearchDao.get_research_job(db, first['jobId'], 7)
    successor.status = 'failed'
    await db.commit()
    second = await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=successor.id)
    assert second['reused'] is False and second['jobId'] != first['jobId']
    assert second['reportId'] == submitted['reportId']
    assert await db.scalar(select(func.count()).select_from(env.models.PipelineResearchJob)) == 3
