"""执行冻结输入；完成时同时检查执行令牌、租约和成果起始版本。"""

import asyncio
from copy import deepcopy
from typing import Any

from app.business_ids import parse_business_id, wire_id
from app.research.models.research_models import PipelineReportVersion, utcnow
from app.research.repositories.research_repository import ResearchDao
from app.research.services.model_generation import ResearchModelGenerationService
from app.research.services.report_content import normalize_generated_report
from config.database import AsyncSessionLocal

HEARTBEAT_INTERVAL_SECONDS = 20
LEASE_SECONDS = 900
MAX_ATTEMPTS = 3


class ResearchExecutionService:
    @staticmethod
    async def _heartbeat(job_id, user_id, token):
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            async with AsyncSessionLocal() as db:
                if not await ResearchDao.touch_research_job(
                    db, job_id, user_id, execution_token=token, lease_seconds=LEASE_SECONDS
                ):
                    return

    @classmethod
    async def process(cls, *, job_id, user_id, owner_name='', stage_labels=(), worker_id='research-worker'):
        async with AsyncSessionLocal() as db:
            job = await ResearchDao.claim_research_job(
                db, job_id, user_id, worker_id=worker_id, lease_seconds=LEASE_SECONDS, max_attempts=MAX_ATTEMPTS
            )
            if not job:
                return
            token = job.execution_token
            snapshot, materials = job.config_snapshot, job.materials
        heartbeat = asyncio.create_task(cls._heartbeat(job_id, user_id, token))
        try:
            async with AsyncSessionLocal() as model_db:
                try:
                    content = await ResearchModelGenerationService.generate_content(
                        model_db, snapshot, materials, task_id=job_id
                    )
                except Exception:
                    await model_db.commit()
                    raise
                await model_db.commit()
            article = normalize_generated_report(content, materials)
            async with AsyncSessionLocal() as result_db:
                job = await ResearchDao.lock_running_research_job(result_db, job_id, user_id, token)
                if not job:
                    return
                report = await ResearchDao.get_report(result_db, job.report_id, user_id, lock=True)
                job.result_content = content
                # 用户已经编辑则仅保存任务结果，绝不悄悄覆盖。
                if report.version == snapshot['report_start_version']:
                    await cls.save_version(result_db, report, 'before_generation', user_id, owner_name)
                    report.content = article['content']
                    report.template_id = parse_business_id(snapshot['template']['id'])
                    report.version += 1
                    report.updated_at = utcnow()
                    await cls.save_version(
                        result_db, report, 'generated', user_id, owner_name, snapshot,
                        sections=article['sections'], citations=cls.material_citations(materials), quality_issues=[],
                    )
                job.status, job.progress, job.finished_at = 'completed', 100, utcnow()
                job.execution_token = job.lease_expires_at = None
                job.error = None
                # 配图作为独立持久资源，失败不会覆盖正文。
                from app.research.services.exports import ResearchReportExportService

                await ResearchReportExportService.queue_images(result_db, job, report)
                await result_db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            async with AsyncSessionLocal() as error_db:
                job = await ResearchDao.lock_running_research_job(error_db, job_id, user_id, token)
                if job:
                    # 不自动重发可能已经计费的未知结果；明确重试由用户决定。
                    job.status, job.error, job.finished_at = (
                        'failed',
                        '生成未完成，请检查模型配置或稍后明确重试',
                        utcnow(),
                    )
                    job.execution_token = job.lease_expires_at = None
                    await error_db.commit()
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)

    @staticmethod
    def material_citations(materials: list[dict] | None) -> list[dict]:
        """真实冻结选材的来源，不将模型输出或模板章节伪装成已核实证据。"""
        return [
            {'id': index, 'type': item['type'], 'sourceId': wire_id(item['id']),
             'title': item.get('title', ''), 'source': deepcopy(item.get('source') or {})}
            for index, item in enumerate(materials or [], 1)
        ]

    @staticmethod
    async def save_version(
        db: Any, report: Any, source: str, user_id: int, owner_name: str, snapshot: dict | None = None, *,
        sections: list[dict] | None = None, citations: list[dict] | None = None,
        quality_issues: list[dict] | None = None,
    ) -> None:
        if await ResearchDao.get_report_version(db, report.id, report.version):
            return
        previous = (await ResearchDao.get_report_version(db, report.id, report.version - 1)
                    if report.version > 1 else None)
        # Missing metadata means preserve; explicit [] means deliberately clear.
        if snapshot is None:
            snapshot = previous.model_snapshot if previous else (
                {'template': {'id': wire_id(report.template_id)}} if report.template_id is not None else {}
            )

        def metadata(value: list[dict] | None, name: str) -> list[dict]:
            return deepcopy(value if value is not None else getattr(previous, name, None) or [])

        await ResearchDao.add_report_version(
            db,
            PipelineReportVersion(
                report_id=report.id,
                version=report.version,
                title=report.title,
                content=report.content,
                source=source,
                operator_id=user_id,
                operator_name=owner_name,
                sections=metadata(sections, 'sections'),
                citations=metadata(citations, 'citations'),
                quality_issues=metadata(quality_issues, 'quality_issues'),
                model_snapshot=deepcopy(snapshot),
            ),
        )
