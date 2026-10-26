"""科研任务恢复调度，弥补进程重启或请求响应丢失造成的队列中断。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.infrastructure.services.logging_support import logger
from app.intelligence.services.templates import PipelineTemplateService
from app.library.tasks.material_parse_scheduler import recover_material_parses, stop_material_parse_tasks
from app.research.models.research_models import utcnow
from app.research.repositories.research_repository import ResearchDao as PipelineDao
from app.research.services.application import ResearchApplicationService
from app.research.services.digest_schedules import DigestScheduleService
from app.research.services.execution import MAX_ATTEMPTS as RESEARCH_MAX_ATTEMPTS
from app.research.services.exports import ResearchReportExportService
from config.database import AsyncSessionLocal

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


JOB_ID = '_pipesight_research_job_recovery'
RECOVERY_INTERVAL_SECONDS = 5
_recovery_tasks: dict[str, asyncio.Task[Any]] = {}
RESEARCH_WORKER_ID = f'task-worker-research-{uuid4().hex[:12]}'
_export_recovery_tasks: dict[str, asyncio.Task[Any]] = {}
EXPORT_JOB_ID = '_pipesight_report_export_recovery'
EXPORT_RECOVERY_INTERVAL_SECONDS = 5
EXPORT_WORKER_ID = f'task-worker-export-{uuid4().hex[:12]}'


async def recover_research_jobs() -> dict[str, int]:
    """扫描持久队列并派发科研任务，领取和租约由数据库行锁最终裁决。"""
    if AsyncSessionLocal is None:
        return {'found': 0, 'dispatched': 0}

    now = utcnow()
    async with AsyncSessionLocal() as db:
        jobs = await PipelineDao.list_research_job_ids_for_dispatch(
            db,
            now=now,
            max_attempts=RESEARCH_MAX_ATTEMPTS,
        )

    dispatched = 0
    for job_id, user_id, owner_name in jobs:
        if job_id in _recovery_tasks:
            continue
        task = asyncio.create_task(
            ResearchApplicationService.process_queued_job(
                job_id=job_id,
                user_id=user_id,
                owner_name=owner_name,
                worker_id=RESEARCH_WORKER_ID,
            )
        )
        _recovery_tasks[job_id] = task

        def _forget(_task: asyncio.Task[Any], item_id: str = job_id) -> None:
            _recovery_tasks.pop(item_id, None)

        task.add_done_callback(_forget)
        dispatched += 1
    if dispatched:
        logger.info(f'科研任务持久队列调度完成，发现 {len(jobs)} 个任务，派发 {dispatched} 个。')
    return {'found': len(jobs), 'dispatched': dispatched}


def register_research_job_recovery(scheduler: AsyncIOScheduler) -> Any:
    """Register one leader-only recovery loop on the existing scheduler."""
    return scheduler.add_job(
        recover_research_jobs,
        trigger='interval',
        seconds=RECOVERY_INTERVAL_SECONDS,
        id=JOB_ID,
        name='科研任务中断恢复',
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


async def recover_report_exports() -> dict[str, int]:
    """扫描到期导出任务，交给租约领取逻辑执行并支持 API 重启恢复。"""
    if AsyncSessionLocal is None:
        return {'found': 0, 'dispatched': 0}

    now = utcnow()
    async with AsyncSessionLocal() as db:
        export_ids = await PipelineDao.list_report_export_ids_for_dispatch(
            db,
            now=now,
            max_attempts=ResearchReportExportService.MAX_ATTEMPTS,
        )

    dispatched = 0
    for export_id in export_ids:
        if export_id in _export_recovery_tasks:
            continue
        task = asyncio.create_task(ResearchReportExportService.process(export_id, EXPORT_WORKER_ID))
        _export_recovery_tasks[export_id] = task

        def _forget(_task: asyncio.Task[Any], item_id: str = export_id) -> None:
            _export_recovery_tasks.pop(item_id, None)

        task.add_done_callback(_forget)
        dispatched += 1
    if dispatched:
        logger.info(f'报告导出恢复调度完成，发现 {len(export_ids)} 个任务，派发 {dispatched} 个。')
    return {'found': len(export_ids), 'dispatched': dispatched}


async def dispatch_digest_schedules() -> dict[str, int]:
    """派发到期的日报、周报和月报计划；计划本身由数据库租约去重。"""
    result = await DigestScheduleService.dispatch_due(
        stage_labels=ResearchApplicationService.stage_labels,
        job_serializer=ResearchApplicationService.job_dict,
        template_service=PipelineTemplateService,
    )
    if result['found']:
        logger.info(
            f'周期简报计划扫描完成，发现 {result["found"]} 个，排队 {result["queued"]} 个，'
            f'无数据 {result["no_data"]} 个，跳过 {result["skipped"]} 个，失败 {result["failed"]} 个。'
        )
    return result


def register_report_export_recovery(scheduler: AsyncIOScheduler) -> Any:
    """在已有的单领导者调度器中注册持久导出任务扫描。"""
    return scheduler.add_job(
        recover_report_exports,
        trigger='interval',
        seconds=EXPORT_RECOVERY_INTERVAL_SECONDS,
        id=EXPORT_JOB_ID,
        name='报告导出任务恢复',
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


async def stop_recovery_tasks() -> None:
    """停止当前进程已派发的持久任务，供 API 和独立 Worker 优雅退出。"""
    tasks = [*_recovery_tasks.values(), *_export_recovery_tasks.values()]
    if not tasks:
        return

    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _recovery_tasks.clear()
    _export_recovery_tasks.clear()
    await stop_material_parse_tasks()


async def run_persistent_recovery_loop(stop_event: asyncio.Event | None = None) -> None:
    """在独立进程中持续恢复科研任务、报告导出和资料解析任务。"""
    stop_event = stop_event or asyncio.Event()
    logger.info('科研任务、报告导出与资料解析独立 Worker 已启动。')
    try:
        while not stop_event.is_set():
            try:
                await recover_research_jobs()
                await recover_report_exports()
                await dispatch_digest_schedules()
                await recover_material_parses()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception('独立任务 Worker 扫描持久队列失败，将在下一轮重试。')

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=RECOVERY_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                continue
    finally:
        await stop_recovery_tasks()
        logger.info('科研任务、报告导出与资料解析独立 Worker 已停止。')
