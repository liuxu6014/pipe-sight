from unittest.mock import AsyncMock, Mock

import pytest

from app.entrypoints import task_worker


@pytest.mark.asyncio
async def test_scoped_worker_entrypoint_never_starts_operational_queues(monkeypatch):
    monkeypatch.setattr(task_worker, 'register_sqlalchemy_models', Mock())
    monkeypatch.setattr(task_worker, 'init_create_table', AsyncMock())
    close, operational, recovery = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(task_worker, 'close_async_engine', close)
    monkeypatch.setattr(task_worker, 'run_operational_scheduler', operational)
    monkeypatch.setattr(task_worker, 'run_persistent_recovery_loop', recovery)
    await task_worker._run_worker(schedule_ids=[86, 95])
    operational.assert_not_awaited()
    recovery.assert_awaited_once()
    assert recovery.await_args.kwargs == {'schedule_ids': [86, 95]}
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_scope_fails_closed(monkeypatch):
    monkeypatch.setattr(task_worker, 'register_sqlalchemy_models', Mock())
    monkeypatch.setattr(task_worker, 'init_create_table', AsyncMock())
    close, operational, recovery = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(task_worker, 'close_async_engine', close)
    monkeypatch.setattr(task_worker, 'run_operational_scheduler', operational)
    monkeypatch.setattr(task_worker, 'run_persistent_recovery_loop', recovery)
    with pytest.raises(ValueError, match='至少指定一个'):
        await task_worker._run_worker(schedule_ids=[])
    operational.assert_not_awaited()
    recovery.assert_not_awaited()
    close.assert_awaited_once()
