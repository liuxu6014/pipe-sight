from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from apscheduler.triggers.cron import CronTrigger

from config.database import AsyncSessionLocal
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.service.pipeline_collection_service import PipelineCollectionService
from utils.log_util import logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


JOB_PREFIX = '_pipesight_collection_'
_source_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def run_scheduled_collection(source_id: str) -> dict[str, Any]:
    """Execute one scheduled source run with a process-local re-entry guard."""
    lock = _source_locks[source_id]
    if lock.locked():
        return {'source_id': source_id, 'status': 'skipped', 'reason': 'already_running'}
    if AsyncSessionLocal is None:
        return {'source_id': source_id, 'status': 'skipped', 'reason': 'database_unavailable'}

    async with lock, AsyncSessionLocal() as db:
        source = await PipelineDao.get_source(db, source_id)
        if not source or not source.enabled or source.status != 'active':
            return {'source_id': source_id, 'status': 'skipped', 'reason': 'source_disabled'}
        try:
            result = await PipelineCollectionService.collect_source(db, source, trigger_type='schedule')
            return {'source_id': source_id, **result}
        except Exception as exc:  # collector persists the failed run before re-raising
            logger.warning(f'管网数据源定时采集失败，source_id={source_id}: {exc}')
            return {'source_id': source_id, 'status': 'failed', 'error': str(exc)[:2000]}


async def register_real_collection_schedules(scheduler: AsyncIOScheduler) -> list[str]:
    """Register active pipeline sources from the database on the elected scheduler leader."""
    if AsyncSessionLocal is None:
        return []

    async with AsyncSessionLocal() as db:
        sources = await PipelineDao.list_sources(db)

    active_job_ids: set[str] = set()
    registered: list[str] = []
    for source in sources:
        job_id = f'{JOB_PREFIX}{source.source_id}'
        if not source.enabled or source.status != 'active' or not source.schedule_cron:
            continue
        try:
            trigger = CronTrigger.from_crontab(source.schedule_cron, timezone='Asia/Shanghai')
        except (TypeError, ValueError) as exc:
            logger.warning(f'跳过无效的数据源调度表达式，source_id={source.source_id}: {exc}')
            continue
        scheduler.add_job(
            run_scheduled_collection,
            trigger=trigger,
            args=[source.source_id],
            id=job_id,
            name=f'{source.name}自动采集',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
        active_job_ids.add(job_id)
        registered.append(source.source_id)

    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX) and job.id not in active_job_ids:
            scheduler.remove_job(job.id)
    return registered
