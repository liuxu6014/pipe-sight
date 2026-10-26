import asyncio
from unittest.mock import AsyncMock

import pytest

from app.intelligence.tasks import operational_scheduler


class _FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.shutdown_called = False
        self.jobs: list[dict[str, object]] = []

    def start(self) -> None:
        self.started = True

    def shutdown(self, *, wait: bool) -> None:
        assert wait is False
        self.shutdown_called = True

    def add_job(self, func: object, **kwargs: object) -> object:
        self.jobs.append({'func': func, **kwargs})
        return kwargs.get('id', 'job')


@pytest.mark.asyncio
async def test_operational_worker_registers_only_collection_refresh_and_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = _FakeScheduler()
    register_collection = AsyncMock(return_value=['source-1'])
    monkeypatch.setattr(operational_scheduler, 'AsyncIOScheduler', lambda: scheduler)
    monkeypatch.setattr(operational_scheduler, 'register_real_collection_schedules', register_collection)

    stop_event = asyncio.Event()

    async def stop_after_first_wait(_event: asyncio.Event, timeout: float) -> None:
        assert timeout == operational_scheduler.OPERATIONAL_REFRESH_INTERVAL_SECONDS
        stop_event.set()

    monkeypatch.setattr(operational_scheduler, '_wait_for_stop', stop_after_first_wait)
    await operational_scheduler.run_operational_scheduler(stop_event)

    assert scheduler.started is True
    assert scheduler.shutdown_called is True
    register_collection.assert_awaited_once_with(scheduler)
    assert not hasattr(operational_scheduler, 'register_insighthub_handoff_polling')
    assert tuple(job['id'] for job in scheduler.jobs) == (
        operational_scheduler.REFRESH_JOB_ID,
        operational_scheduler.QUEUED_COLLECTION_JOB_ID,
    )
    assert scheduler.jobs[1]['seconds'] == operational_scheduler.QUEUED_COLLECTION_POLL_INTERVAL_SECONDS
    assert scheduler.jobs[1]['func'] is operational_scheduler.run_queued_collections


@pytest.mark.asyncio
async def test_operational_worker_stops_scheduler_when_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = _FakeScheduler()
    monkeypatch.setattr(operational_scheduler, 'AsyncIOScheduler', lambda: scheduler)
    monkeypatch.setattr(operational_scheduler, 'register_real_collection_schedules', AsyncMock())

    async def cancel_wait(_event: asyncio.Event, _timeout: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(operational_scheduler, '_wait_for_stop', cancel_wait)

    with pytest.raises(asyncio.CancelledError):
        await operational_scheduler.run_operational_scheduler(asyncio.Event())

    assert scheduler.shutdown_called is True
