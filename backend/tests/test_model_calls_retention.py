"""model_calls 保留期清理的离线验证：用假会话记录 SQL，不连真实数据库。"""

import pytest

from app.intelligence.tasks.model_calls_retention import (
    MODEL_CALLS_FAILED_RETENTION_DAYS,
    MODEL_CALLS_RETENTION_BATCH,
    MODEL_CALLS_SUCCESS_RETENTION_DAYS,
    purge_expired_model_calls,
)


class _FakeResult:
    def __init__(self, scalar_value=None, rowcount=0):
        self._scalar = scalar_value
        self.rowcount = rowcount

    def scalar(self):
        return self._scalar


class _FakeSession:
    def __init__(self, results):
        self._results = list(results)
        self.calls = []
        self.committed = 0

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params or {}))
        return self._results.pop(0)

    async def commit(self):
        self.committed += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _delete_params(call):
    return call[1]


@pytest.mark.asyncio
async def test_purge_skips_when_another_worker_holds_lock() -> None:
    session = _FakeSession([_FakeResult(scalar_value=False)])
    deleted = await purge_expired_model_calls(sessions=lambda: session)

    assert deleted == 0
    # 只执行了一次锁获取，没有删除也没有解锁。
    assert len(session.calls) == 1
    assert 'pg_try_advisory_lock' in session.calls[0][0]


@pytest.mark.asyncio
async def test_purge_deletes_success_and_failed_with_correct_windows() -> None:
    # 锁获取 → success 两批(5000 满批 + 0 停) → failed 两批 → 解锁
    session = _FakeSession(
        [
            _FakeResult(scalar_value=True),  # lock
            _FakeResult(rowcount=MODEL_CALLS_RETENTION_BATCH),  # success batch 1
            _FakeResult(rowcount=0),  # success batch 2 停
            _FakeResult(rowcount=MODEL_CALLS_RETENTION_BATCH),  # failed batch 1
            _FakeResult(rowcount=0),  # failed batch 2 停
            _FakeResult(scalar_value=True),  # unlock
        ]
    )
    deleted = await purge_expired_model_calls(sessions=lambda: session)

    assert deleted == MODEL_CALLS_RETENTION_BATCH * 2
    delete_calls = [c for c in session.calls if 'DELETE FROM model_calls' in c[0]]
    assert len(delete_calls) == 4
    assert _delete_params(delete_calls[0])['status'] == 'success'
    assert _delete_params(delete_calls[0])['days'] == MODEL_CALLS_SUCCESS_RETENTION_DAYS
    assert _delete_params(delete_calls[2])['status'] == 'failed'
    assert _delete_params(delete_calls[2])['days'] == MODEL_CALLS_FAILED_RETENTION_DAYS
    # 每个删除 SQL 都用北京墙钟算 cutoff，而不是 UTC。
    for call in delete_calls:
        assert "CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai'" in call[0]
    # finally 里必须显式解锁。
    assert any('pg_advisory_unlock' in c[0] for c in session.calls)


@pytest.mark.asyncio
async def test_purge_releases_lock_when_delete_raises() -> None:
    session = _FakeSession([_FakeResult(scalar_value=True), _FakeResult(rowcount=0)])

    async def broken_execute(stmt, params=None):
        session.calls.append((str(stmt), params or {}))
        if 'DELETE FROM model_calls' in str(stmt):
            raise RuntimeError('delete exploded')
        return _FakeResult(scalar_value=True)

    session.execute = broken_execute

    with pytest.raises(RuntimeError):
        await purge_expired_model_calls(sessions=lambda: session)

    assert any('pg_advisory_unlock' in c[0] for c in session.calls)
