"""管网 canonical 数据采集的独立任务 Worker 调度。"""

from __future__ import annotations

import asyncio
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infrastructure.services.logging_support import logger
from app.intelligence.tasks.collection_scheduler import register_real_collection_schedules, run_queued_collections

# Keep the refresh job outside JOB_PREFIX from collection_scheduler.  That
# prefix is intentionally reserved for per-source jobs; using it here makes
# register_real_collection_schedules remove this job while pruning stale
# source schedules.
REFRESH_JOB_ID = '_pipesight_schedule_refresh'
QUEUED_COLLECTION_JOB_ID = '_pipesight_queued_collection_poll'
OPERATIONAL_REFRESH_INTERVAL_SECONDS = 60
QUEUED_COLLECTION_POLL_INTERVAL_SECONDS = 10


async def _wait_for_stop(stop_event: asyncio.Event, timeout: float) -> None:
    """等待退出信号；单独抽出便于测试和保证取消语义。"""
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return


async def _refresh_collection_schedules(scheduler: Any) -> None:
    registered = await register_real_collection_schedules(scheduler)
    if registered:
        logger.info(f'独立 Worker 已刷新数据源采集调度，激活 {len(registered)} 个来源。')


async def run_operational_scheduler(stop_event: asyncio.Event | None = None) -> None:
    """在独立进程中运行数据采集队列及数据源调度刷新。"""
    stop_event = stop_event or asyncio.Event()
    scheduler = AsyncIOScheduler()
    scheduler.start()
    try:
        await _refresh_collection_schedules(scheduler)
        scheduler.add_job(
            _refresh_collection_schedules,
            trigger='interval',
            seconds=OPERATIONAL_REFRESH_INTERVAL_SECONDS,
            args=[scheduler],
            id=REFRESH_JOB_ID,
            name='数据源采集调度刷新',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        scheduler.add_job(
            run_queued_collections,
            trigger='interval',
            seconds=QUEUED_COLLECTION_POLL_INTERVAL_SECONDS,
            id=QUEUED_COLLECTION_JOB_ID,
            name='手动采集队列执行器',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        logger.info('数据采集独立 Worker 已启动。')
        while not stop_event.is_set():
            await _wait_for_stop(stop_event, OPERATIONAL_REFRESH_INTERVAL_SECONDS)
    finally:
        scheduler.shutdown(wait=False)
        logger.info('数据采集独立 Worker 已停止。')


__all__ = ['run_operational_scheduler']
