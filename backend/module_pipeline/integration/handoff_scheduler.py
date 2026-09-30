from __future__ import annotations

from typing import TYPE_CHECKING, Any

from config.database import AsyncSessionLocal
from config.env import InsightHubConfig
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.service.pipeline_domain_service import PipelineDomainService
from utils.log_util import logger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


JOB_ID = '_pipesight_insighthub_handoff_poll'


async def poll_insighthub_handoff() -> dict[str, int]:
    """Poll dispatched InsightHub runs and persist their receipts locally."""
    if not InsightHubConfig.insighthub_enabled or AsyncSessionLocal is None:
        return {'runs': 0, 'synced': 0, 'failed': 0}

    synced = failed = 0
    async with AsyncSessionLocal() as db:
        runs = await PipelineDao.list_pending_handoff_runs(db)
        for run in runs:
            if await _sync_run(db, run.run_id):
                synced += 1
            else:
                failed += 1
    return {'runs': len(runs), 'synced': synced, 'failed': failed}


async def _sync_run(db: Any, run_id: str) -> bool:
    try:
        await PipelineDomainService.sync_insighthub_handoff(db, run_id)
    except Exception as exc:
        await db.rollback()
        logger.warning(f'InsightHub 回执同步失败，run_id={run_id}: {exc}')
        return False
    return True


def register_insighthub_handoff_polling(scheduler: AsyncIOScheduler) -> Any:
    """Register one leader-only polling job; no schema or queue table is added."""
    if not InsightHubConfig.insighthub_enabled:
        return None
    return scheduler.add_job(
        poll_insighthub_handoff,
        trigger='interval',
        seconds=InsightHubConfig.insighthub_poll_interval_seconds,
        id=JOB_ID,
        name='InsightHub处理回执同步',
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


async def finalize_collection_run(db: Any, run_id: str) -> dict[str, Any]:
    """Hook for the real collector: finish a run, then submit external articles."""
    run = await PipelineDao.get_collection_run(db, run_id)
    if not run:
        raise ValueError('采集运行不存在')
    run.status = 'success'
    result = await PipelineDomainService.dispatch_insighthub_handoff(db, run_id)
    await db.commit()
    result['collection_status'] = run.status
    return result
