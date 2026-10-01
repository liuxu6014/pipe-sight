import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.integration import collection_scheduler


class _FakeSession:
    async def __aenter__(self) -> '_FakeSession':
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.removed: list[str] = []

    def add_job(self, func: object, **kwargs: object) -> object:
        self.jobs.append({'func': func, **kwargs})
        return kwargs['id']

    def get_jobs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=item['id']) for item in self.jobs] + [
            SimpleNamespace(id=f'{collection_scheduler.JOB_PREFIX}disabled')
        ]

    def remove_job(self, job_id: str) -> None:
        self.removed.append(job_id)


@pytest.mark.asyncio
async def test_scheduled_collection_uses_schedule_trigger_and_removes_disabled_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = [
        SimpleNamespace(
            source_id='src-pipechina',
            name='国家管网集团要闻',
            enabled=True,
            status='active',
            schedule_cron='0 */6 * * *',
        ),
        SimpleNamespace(
            source_id='src-disabled',
            name='已停用来源',
            enabled=False,
            status='inactive',
            schedule_cron='0 * * * *',
        ),
    ]
    monkeypatch.setattr(collection_scheduler, 'AsyncSessionLocal', _FakeSession)
    monkeypatch.setattr(PipelineDao, 'list_sources', AsyncMock(return_value=sources))

    scheduler = _FakeScheduler()
    result = await collection_scheduler.register_real_collection_schedules(scheduler)

    assert result == ['src-pipechina']
    assert scheduler.jobs[0]['id'] == f'{collection_scheduler.JOB_PREFIX}src-pipechina'
    assert scheduler.jobs[0]['args'] == ['src-pipechina']
    assert scheduler.jobs[0]['trigger'].timezone.key == 'Asia/Shanghai'
    assert scheduler.removed == [f'{collection_scheduler.JOB_PREFIX}disabled']


@pytest.mark.asyncio
async def test_scheduled_collection_skips_reentry_and_persists_failure_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SimpleNamespace(source_id='src-1', name='来源', enabled=True, status='active')
    monkeypatch.setattr(collection_scheduler, 'AsyncSessionLocal', _FakeSession)
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=source))

    started = asyncio.Event()
    release = asyncio.Event()

    async def collect(*_args: object, **_kwargs: object) -> dict:
        started.set()
        await release.wait()
        raise RuntimeError('upstream unavailable')

    monkeypatch.setattr(collection_scheduler.PipelineCollectionService, 'collect_source', collect)
    first = asyncio.create_task(collection_scheduler.run_scheduled_collection('src-1'))
    await started.wait()
    second = await collection_scheduler.run_scheduled_collection('src-1')
    release.set()
    first_result = await first

    assert second == {'source_id': 'src-1', 'status': 'skipped', 'reason': 'already_running'}
    assert first_result['status'] == 'failed'
    assert first_result['error'] == 'upstream unavailable'
