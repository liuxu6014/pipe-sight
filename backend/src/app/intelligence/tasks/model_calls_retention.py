"""model_calls 用量记录保留期清理：成功 30 天 / 失败 90 天，每日低峰批量删除。

排障只依赖失败记录（error 摘要），成功明细没有消费方，保留窗口保持 30 天即可；
失败记录保留 90 天以覆盖跨月回溯。清理不改写任何业务数据，也不改动 model_calls 的
表结构或冻结契约。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

MODEL_CALLS_SUCCESS_RETENTION_DAYS = 30
MODEL_CALLS_FAILED_RETENTION_DAYS = 90
MODEL_CALLS_RETENTION_BATCH = 5000
# 首次运行可能积压大量过期行；单次运行设批数上限，跨几天自然排空，避免一次刷爆 WAL。
MODEL_CALLS_RETENTION_MAX_BATCHES = 50
# 多副本 worker 之间用会话级 advisory lock 串行化，避免并发删除同一批行。
MODEL_CALLS_RETENTION_LOCK_KEY = 842001
MODEL_CALLS_RETENTION_JOB_ID = '_pipesight_model_calls_retention'

# created_at 是 BeijingAuditTime（PG timestamp(0) without time zone，北京墙钟），
# 必须用北京墙钟算 cutoff，不能按 UTC，否则会多删/少删 8 小时窗口。
_DELETE_SQL = """
WITH doomed AS (
  SELECT id FROM model_calls
  WHERE status = :status
    AND created_at < date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')
                    - (:days * INTERVAL '1 day')
  LIMIT :batch
)
DELETE FROM model_calls WHERE id IN (SELECT id FROM doomed);
"""


def session_factory() -> Any:
    # 仅导入本模块不会初始化数据库引擎；运行时再解析 AsyncSessionLocal。
    from config.database import AsyncSessionLocal  # noqa: PLC0415

    return AsyncSessionLocal


async def purge_expired_model_calls(*, sessions: Any = None) -> int:
    """删除过期的 model_calls 明细，返回删除行数；未取得锁或无法建会话则返回 0。"""
    sessions = sessions or session_factory()
    if sessions is None:
        return 0
    async with sessions() as db:
        acquired = await db.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': MODEL_CALLS_RETENTION_LOCK_KEY})
        if not acquired.scalar():
            # 另一个 worker 副本正在清理；本周期跳过即可。
            return 0
        deleted = 0
        try:
            for status, days in (
                ('success', MODEL_CALLS_SUCCESS_RETENTION_DAYS),
                ('failed', MODEL_CALLS_FAILED_RETENTION_DAYS),
            ):
                for _ in range(MODEL_CALLS_RETENTION_MAX_BATCHES):
                    result = await db.execute(
                        text(_DELETE_SQL),
                        {'status': status, 'days': days, 'batch': MODEL_CALLS_RETENTION_BATCH},
                    )
                    await db.commit()
                    count = result.rowcount or 0
                    deleted += count
                    if count < MODEL_CALLS_RETENTION_BATCH:
                        break
        finally:
            await db.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': MODEL_CALLS_RETENTION_LOCK_KEY})
            await db.commit()
        if deleted:
            logger.info('model_calls 保留期清理完成，删除 %d 行。', deleted)
        return deleted


__all__ = [
    'MODEL_CALLS_RETENTION_JOB_ID',
    'purge_expired_model_calls',
]
