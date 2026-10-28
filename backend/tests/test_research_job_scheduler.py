import asyncio

import pytest

from app.research.tasks import research_job_scheduler


@pytest.mark.asyncio
async def test_scoped_loop_never_runs_unrelated_export_or_parse_queues(monkeypatch):
    from unittest.mock import AsyncMock
    stop = asyncio.Event()
    research, dispatch = AsyncMock(), AsyncMock()
    async def scoped_dispatch(**kwargs):
        await dispatch(**kwargs)
        stop.set()
    monkeypatch.setattr(research_job_scheduler, 'recover_research_jobs', research)
    monkeypatch.setattr(research_job_scheduler, 'dispatch_digest_schedules', scoped_dispatch)
    exports, parses = AsyncMock(), AsyncMock()
    monkeypatch.setattr(research_job_scheduler, 'recover_report_exports', exports)
    monkeypatch.setattr(research_job_scheduler, 'recover_material_parses', parses)
    await research_job_scheduler.run_persistent_recovery_loop(stop, schedule_ids=[86])
    research.assert_awaited_once_with(schedule_ids=[86])
    dispatch.assert_awaited_once_with(schedule_ids=[86])
    exports.assert_not_awaited()
    parses.assert_not_awaited()


@pytest.mark.asyncio
async def test_persistent_recovery_loop_scans_both_queues_and_stops() -> None:
    stop_event = asyncio.Event()
    calls: list[str] = []

    async def recover_research() -> dict[str, int]:
        calls.append('research')
        return {'found': 1, 'dispatched': 1}

    async def recover_exports() -> dict[str, int]:
        calls.append('exports')
        stop_event.set()
        return {'found': 1, 'dispatched': 1}

    original_research = research_job_scheduler.recover_research_jobs
    original_exports = research_job_scheduler.recover_report_exports
    research_job_scheduler.recover_research_jobs = recover_research
    research_job_scheduler.recover_report_exports = recover_exports
    try:
        await research_job_scheduler.run_persistent_recovery_loop(stop_event)
    finally:
        research_job_scheduler.recover_research_jobs = original_research
        research_job_scheduler.recover_report_exports = original_exports

    assert calls == ['research', 'exports']


@pytest.mark.asyncio
async def test_stop_recovery_tasks_cancels_inflight_research_and_export_tasks() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def pending_task() -> None:
        started.set()
        await release.wait()

    task = asyncio.create_task(pending_task())
    await started.wait()
    research_job_scheduler._recovery_tasks['research-1'] = task

    try:
        await research_job_scheduler.stop_recovery_tasks()
        assert task.cancelled()
        assert research_job_scheduler._recovery_tasks == {}
        assert research_job_scheduler._export_recovery_tasks == {}
    finally:
        release.set()
        research_job_scheduler._recovery_tasks.clear()
        research_job_scheduler._export_recovery_tasks.clear()
