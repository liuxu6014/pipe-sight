"""APScheduler 仅唤醒来源游标扫描器、执行器和租约恢复器。"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.intelligence.models.collection import PipelineCrawlRun as Run
from app.intelligence.models.collection import PipelineSource as Source
from app.intelligence.repositories.collection_repository import CollectionRepository
from app.intelligence.services.collection import ADAPTERS, PipelineCollectionService
from app.intelligence.services.sources import IntelligenceSourceService

JOB_PREFIX = '_pipesight_collection_'
logger = logging.getLogger(__name__)


def session_factory() -> Any:
    # Merely importing this module never initializes a database engine.
    from config.database import AsyncSessionLocal  # noqa: PLC0415

    return AsyncSessionLocal


async def run_scheduled_collection(source_id: int, *, sessions: Any = None, registry: dict = ADAPTERS) -> Any:
    sessions = sessions or session_factory()
    async with sessions() as db:
        return await IntelligenceSourceService.schedule_due_source(db, source_id, registry=registry)


async def scan_due_sources(*, sessions: Any = None, registry: dict = ADAPTERS) -> list:
    sessions = sessions or session_factory()
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        ids = list(
            (
                await db.execute(
                    select(Source.id)
                    .where(Source.is_enabled.is_(True), Source.next_run_at <= now)
                    .order_by(Source.next_run_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
    results = []
    for source_id in ids:
        try:
            results.append(await run_scheduled_collection(source_id, sessions=sessions, registry=registry))
        except Exception:  # noqa: PERF203 (per-item isolation for a batch job)
            logger.warning('来源调度失败，source_id=%s；检查来源配置', source_id)
    return results


async def run_queued_collection(run_id: int, *, sessions: Any = None, registry: dict = ADAPTERS) -> Any:
    sessions = sessions or session_factory()
    async with sessions() as db:
        return await PipelineCollectionService.execute(db, run_id, registry=registry)


async def run_queued_collections(*, sessions: Any = None, registry: dict = ADAPTERS) -> list:
    sessions = sessions or session_factory()
    async with sessions() as db:
        ids = await CollectionRepository.ready(db, datetime.now(timezone.utc))
    results = []
    for run_id in ids:
        try:
            results.append(await run_queued_collection(run_id, sessions=sessions, registry=registry))
        except Exception:  # noqa: PERF203 (per-item isolation for a batch job)
            logger.warning('采集执行器异常，run_id=%s；由租约恢复器处理', run_id)
    return results


async def recover_expired_collections(*, sessions: Any = None, registry: dict = ADAPTERS) -> list[dict]:
    sessions = sessions or session_factory()
    now = datetime.now(timezone.utc)
    async with sessions() as db:
        ids = list(
            (
                await db.execute(
                    select(Run.id)
                    .where(Run.status.in_(('running', 'stopping')), Run.lease_expires_at <= now)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
    results = []
    for run_id in ids:
        async with sessions() as db:
            run = await CollectionRepository.recover(db, run_id, now=now)
            results.append({'id': run_id, 'status': run.status})
            if run.status == 'failed':
                await IntelligenceSourceService.retry_collection_run(db, run_id, automatic=True, registry=registry)
    return results


async def register_real_collection_schedules(scheduler: Any) -> list[str]:
    """Install generic wakeups. No source bootstrap and no immediate collection."""
    jobs = {
        'scan': (scan_due_sources, 15),
        'execute': (run_queued_collections, 5),
        'recover': (recover_expired_collections, 15),
    }
    ids = {f'{JOB_PREFIX}{key}' for key in jobs}
    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX) and job.id not in ids:
            scheduler.remove_job(job.id)
    for key, (function, seconds) in jobs.items():
        scheduler.add_job(
            function,
            'interval',
            seconds=seconds,
            id=f'{JOB_PREFIX}{key}',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
    return sorted(ids)
