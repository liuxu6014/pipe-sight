from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.integration import handoff_scheduler
from module_pipeline.integration.handoff_scheduler import JOB_ID


@pytest.mark.asyncio
async def test_poll_skips_when_external_processing_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handoff_scheduler.InsightHubConfig, 'insighthub_enabled', False)

    result = await handoff_scheduler.poll_insighthub_handoff()

    assert result == {'runs': 0, 'synced': 0, 'failed': 0}


def test_register_polling_adds_one_replaceable_interval_job(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeScheduler:
        def __init__(self) -> None:
            self.kwargs = None

        def add_job(self, *_args: object, **kwargs: object) -> object:
            self.kwargs = kwargs
            return 'job'

    scheduler = FakeScheduler()
    monkeypatch.setattr(handoff_scheduler.InsightHubConfig, 'insighthub_enabled', True)
    monkeypatch.setattr(handoff_scheduler.InsightHubConfig, 'insighthub_poll_interval_seconds', 15)

    assert handoff_scheduler.register_insighthub_handoff_polling(scheduler) == 'job'
    assert scheduler.kwargs == {
        'trigger': 'interval',
        'seconds': 15,
        'id': JOB_ID,
        'name': 'InsightHub处理回执同步',
        'replace_existing': True,
        'coalesce': True,
        'max_instances': 1,
    }


@pytest.mark.asyncio
async def test_poll_syncs_each_pending_run_and_continues_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [SimpleNamespace(run_id='run-1'), SimpleNamespace(run_id='run-2')]
    monkeypatch.setattr(handoff_scheduler.InsightHubConfig, 'insighthub_enabled', True)
    monkeypatch.setattr(handoff_scheduler, 'AsyncSessionLocal', _FakeSession)
    monkeypatch.setattr(PipelineDao, 'list_pending_handoff_runs', AsyncMock(return_value=runs))

    sync = AsyncMock(side_effect=[None, RuntimeError('temporary')])
    monkeypatch.setattr(handoff_scheduler.PipelineDomainService, 'sync_insighthub_handoff', sync)

    result = await handoff_scheduler.poll_insighthub_handoff()

    assert result == {'runs': len(runs), 'synced': 1, 'failed': 1}
    assert sync.await_count == len(runs)


class _FakeSession:
    async def __aenter__(self) -> '_FakeSession':
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def rollback(self) -> None:
        return None
