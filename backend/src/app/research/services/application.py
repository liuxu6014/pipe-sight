"""科研 API 的应用编排、权限结果和兼容字段适配。"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from app.business_ids import wire_id
from app.business_time import format_business_time
from app.intelligence.services.templates import PipelineTemplateService
from app.research.repositories.research_repository import ResearchDao as PipelineDao
from app.research.services.digest_schedules import DigestScheduleService
from app.research.services.execution import ResearchExecutionService
from app.research.services.exports import ResearchReportExportService
from app.research.services.jobs import ResearchJobService
from app.research.services.report_content import normalize_generated_report, number_report_citations, sections_from_markdown
from app.research.services.report_revision import report_revision
from app.research.services.reports import ResearchReportService
from app.research.services.workspace import ResearchWorkspaceService
from exceptions.exception import ServiceException

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.intelligence.schemas.pipeline import (
        PipelineDiagramUpdateModel,
        PipelineDigestScheduleCreateModel,
        PipelineReportUpdateModel,
        PipelineResearchJobCreateModel,
        PipelineWorkspaceItemMutationModel,
    )


class ResearchApplicationService:
    """科研工作区、任务和报告 API 的应用服务。"""

    stage_labels = [
        ('validating', '资料校验'),
        ('parsing', '资料解析'),
        ('retrieving', '证据检索'),
        ('outlining', '大纲规划'),
        ('writing', '章节生成'),
        ('citation_check', '引用校验'),
        ('quality_check', '质量检查'),
        ('diagram', '图形准备'),
        ('completed', '任务完成'),
    ]

    @staticmethod
    def _datetime_text(value: datetime | None) -> str:
        return format_business_time(value)

    @classmethod
    def _execution_display(cls, job, apply_conflict=False):
        """Expose only persisted lifecycle facts, not an invented fine-grained pipeline."""
        status = job.status
        terminal = status in {'completed', 'failed', 'cancelled'}
        has_result = bool((job.result_content or '').strip())
        result_status = ('completed' if has_result else 'failed') if status == 'completed' else (
            'skipped' if terminal else 'waiting'
        )
        result_description = ('生成结果已保存；当前报告内容与本次结果不同' if apply_conflict
                              else '生成结果已保存' if has_result else '等待生成结果保存')
        if terminal and not has_result:
            result_description = '没有已保存的生成结果'
        stages = [
            {'key': 'submitted', 'label': '任务提交', 'status': 'completed',
             'description': '任务及输入资料快照已保存'},
            {'key': 'execution', 'label': '后台执行', 'status': 'waiting' if status == 'queued' else status,
             'description': '按提交配置执行正文生成与结果保存'},
            {'key': 'result', 'label': '结果保存', 'status': result_status, 'description': result_description},
        ]
        logs = []
        if job.created_at:
            logs.append({'time': cls._datetime_text(job.created_at), 'type': 'info', 'message': '任务已提交'})
        if job.started_at:
            logs.append({'time': cls._datetime_text(job.started_at), 'type': 'info', 'message': '后台已开始执行'})
        if terminal:
            message = ({'completed': result_description, 'failed': job.error or '任务生成失败',
                        'cancelled': '任务已取消，不再等待执行结果'})[status]
            logs.append({'time': cls._datetime_text(job.finished_at or job.updated_at),
                         'type': 'error' if status == 'failed' else 'info', 'message': message})
        return {'stages': stages, 'logs': logs,
                'generationMode': 'model' if (job.config_snapshot or {}).get('model') else 'unrecorded',
                'startedAt': cls._datetime_text(job.started_at), 'finishedAt': cls._datetime_text(job.finished_at)}

    @classmethod
    def job_dict(cls, job, report_id=None, report=None):
        snapshot = job.config_snapshot or {}
        request = snapshot.get('request') or {}
        # Match generation_outline: an explicitly submitted outline takes precedence,
        # including an empty list. Only older tasks without it use template sections.
        outline = request['outline'] if 'outline' in request else snapshot.get('template', {}).get('sections', [])
        labels = {
            'queued': '等待生成',
            'running': '生成中',
            'completed': '已完成',
            'failed': '生成失败',
            'cancelled': '已取消',
        }
        normalized_result = job.result_content
        if job.result_content:
            try:
                normalized_result = normalize_generated_report(job.result_content, job.materials, delivery=True)['content']
            except ValueError:
                # Keep malformed raw output inspectable; never call it applied.
                pass
        apply_conflict = bool(job.status == 'completed' and report and report.content != normalized_result)
        return {
            'id': wire_id(job.id),
            'jobId': wire_id(job.id),
            'requestId': job.request_id,
            'reportId': wire_id(job.report_id),
            'title': snapshot.get('title', ''),
            'templateName': (snapshot.get('template') or {}).get('name') or '',
            'type': snapshot.get('type', ''),
            'status': job.status,
            'statusLabel': labels.get(job.status, job.status),
            'stage': job.status,
            'progress': job.progress,
            'ownerId': report.user_id if report else None,
            'owner': '',
            'reportStatus': 'completed' if report and report.content else 'draft',
            'selectedItems': job.materials,
            'outline': deepcopy(outline),
            **cls._execution_display(job, apply_conflict),
            'config': request,
            'errorMessage': job.error or '',
            'attemptCount': job.attempts,
            'cancelRequested': False,
            'nextRetryAt': '',
            'resultContent': normalized_result,
            'applyConflict': apply_conflict,
            'createdAt': cls._datetime_text(job.created_at),
            'updatedAt': cls._datetime_text(job.updated_at),
        }

    @classmethod
    def report_dict(cls, report):
        # 旧 status 只为 API 展示派生，不存在 reports.status 列。
        normalized = (normalize_generated_report(report.content) if report.content.strip()
                      else {'content': '', 'sections': sections_from_markdown('')})
        history = ResearchReportService.current_history(report)
        citations = deepcopy(history.citations or []) if history else []
        normalized['content'] = number_report_citations(normalized['content'], citations)
        normalized['sections'] = sections_from_markdown(normalized['content'])
        raw_sections = deepcopy(history.sections or []) if history else []
        for section in raw_sections:
            section['content'] = number_report_citations(str(section.get('content') or ''), citations)
        # Empty legacy metadata must not hide a real article. Content-only edits
        # may inherit provenance, but old section bodies cannot replace new text.
        if not raw_sections or any(str(section.get('content') or '').strip() not in normalized['content']
                                   for section in raw_sections):
            raw_sections = normalized['sections']
        sections = cls._editor_sections(raw_sections, citations)
        metadata = ResearchReportService.export_snapshot(report, history)['metadata'] if history else {}
        return {
            'id': wire_id(report.id),
            'reportId': wire_id(report.id),
            'title': report.title,
            'type': report.type,
            'reportType': report.type,
            'ownerId': report.user_id,
            'owner': '',
            'jobId': None,
            'templateId': wire_id(report.template_id),
            'status': 'completed' if report.content else 'draft',
            'statusLabel': '已保存',
            'version': f'V{report.version}.0',
            'versionNo': report.version,
            'content': normalized['content'],
            'sections': sections,
            'citations': citations,
            'qualityIssues': deepcopy(history.quality_issues or []) if history else [],
            'metadata': metadata,
            'requiresReview': False,
            'words': len(''.join(normalized['content'].split())),
            'sources': len(citations),
            'coverage': 0,
            'updatedAt': cls._datetime_text(report.updated_at),
            'updated_at': cls._datetime_text(report.updated_at),
            'revision': report_revision(report),
            'createdAt': cls._datetime_text(report.created_at),
        }

    @staticmethod
    def _editor_sections(sections: list[dict], citations: list[dict]) -> list[dict]:
        available = {str(c['id']): c['id'] for c in citations if c.get('id') is not None}
        by_source = {}
        for citation in citations:
            if citation.get('sourceId') is not None and citation.get('id') is not None:
                by_source.setdefault(str(citation['sourceId']), []).append(citation)
        for section in sections:
            body = str(section.get('content') or '')
            ids = [available[str(identity)] for identity in section.get('citationIds', [])
                   if str(identity) in available]
            ordinals = {str(index): citation['id'] for index, citation in enumerate(citations, 1)
                        if citation.get('id') is not None}
            ids.extend(ordinals[identity] for identity in re.findall(r'\[(\d+)\]', body) if identity in ordinals)
            for identity in re.findall(r'\[资料(\d+)\]', body):
                matches = by_source.get(identity, [])
                if len(matches) == 1:
                    ids.append(matches[0]['id'])
            for kind, identity in re.findall(r'\[(article|paper|file):(\d+)\]', body):
                matches = [c for c in by_source.get(identity, []) if c.get('type') == kind]
                if len(matches) == 1:
                    ids.append(matches[0]['id'])
            section['words'] = len(''.join(body.split()))
            section['citationIds'] = list(dict.fromkeys(ids))
        return sections

    @classmethod
    async def list_workspace(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        return await ResearchWorkspaceService.list_items(db, user_id)

    @classmethod
    async def upsert_workspace_item(
        cls,
        db: AsyncSession,
        user_id: int,
        payload: PipelineWorkspaceItemMutationModel,
    ) -> dict[str, Any]:
        return await ResearchWorkspaceService.upsert_item(db, user_id, payload)

    @classmethod
    async def delete_workspace_item(
        cls,
        db: AsyncSession,
        user_id: int,
        item_id: str,
        action: str,
    ) -> dict[str, Any]:
        return await ResearchWorkspaceService.delete_item(db, user_id, item_id, action)

    @classmethod
    async def queue_job(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        payload: PipelineResearchJobCreateModel,
    ) -> dict[str, Any]:
        return await ResearchJobService.queue(
            db,
            user_id=user_id,
            owner_name=owner_name,
            payload=payload,
            stage_labels=cls.stage_labels,
            job_serializer=cls.job_dict,
            template_service=PipelineTemplateService,
        )

    @classmethod
    async def create_digest_schedule(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        payload: PipelineDigestScheduleCreateModel,
    ) -> dict[str, Any]:
        return await DigestScheduleService.create(
            db,
            user_id=user_id,
            owner_name=owner_name,
            payload=payload,
            template_service=PipelineTemplateService,
        )

    @classmethod
    async def list_digest_schedules(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        return await DigestScheduleService.list(db, user_id)

    @classmethod
    async def update_digest_schedule(cls, db, user_id, schedule_id, payload):
        return await DigestScheduleService.update(db, user_id=user_id, schedule_id=schedule_id,
                                                 payload=payload, template_service=PipelineTemplateService)

    @classmethod
    async def set_digest_schedule_enabled(
        cls, db: AsyncSession, user_id: int, schedule_id: str, enabled: bool
    ) -> dict[str, Any]:
        return await DigestScheduleService.set_enabled(db, user_id, schedule_id, enabled)

    @classmethod
    async def run_digest_schedule_now(cls, db: AsyncSession, user_id: int, schedule_id: str) -> dict[str, Any]:
        return await DigestScheduleService.run_now(db, user_id, schedule_id)

    @classmethod
    async def delete_digest_schedule(cls, db: AsyncSession, user_id: int, schedule_id: str) -> None:
        await DigestScheduleService.delete(db, user_id, schedule_id)

    @classmethod
    async def queue_retry(cls, db: AsyncSession, *, user_id: int, job_id: str) -> dict[str, Any]:
        return await ResearchJobService.retry(
            db,
            user_id=user_id,
            job_id=job_id,
            stage_labels=cls.stage_labels,
            job_serializer=cls.job_dict,
        )

    @classmethod
    async def process_queued_job(
        cls,
        *,
        job_id: str,
        user_id: int,
        owner_name: str,
        worker_id: str = 'api-research-worker',
    ) -> None:
        await ResearchExecutionService.process(
            job_id=job_id,
            user_id=user_id,
            owner_name=owner_name,
            stage_labels=cls.stage_labels,
            worker_id=worker_id,
        )

    @classmethod
    async def list_jobs(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        rows = await PipelineDao.list_research_jobs(db, user_id)
        result = []
        for job in rows:
            report = await PipelineDao.get_report(db, job.report_id, user_id)
            result.append(cls.job_dict(job, report=report))
        return {'rows': result, 'total': len(result)}

    @classmethod
    async def get_job(cls, db, user_id, job_id):
        job = await PipelineDao.get_research_job(db, job_id, user_id)
        if not job:
            raise ServiceException(message='任务不存在或无权访问')
        report = await PipelineDao.get_report(db, job.report_id, user_id)
        return cls.job_dict(job, report=report)

    @classmethod
    async def cancel_job(cls, db: AsyncSession, user_id: int, job_id: str) -> dict[str, Any]:
        return await ResearchJobService.cancel(
            db,
            user_id=user_id,
            job_id=job_id,
            job_serializer=cls.job_dict,
        )

    @classmethod
    async def list_admin_reports(cls, db: AsyncSession) -> dict[str, Any]:
        """Read-only management scope; the API requires both admin role and list permission."""
        rows = await PipelineDao.list_admin_reports(db)
        for row in rows:
            await ResearchReportService._load_display_history(db, row)
        return {'rows': [cls.report_dict(row) for row in rows], 'total': len(rows)}

    @classmethod
    async def list_reports(
        cls,
        db: AsyncSession,
        user_id: int,
        *,
        include_all: bool = False,
    ) -> dict[str, Any]:
        return await ResearchReportService.list_reports(
            db,
            user_id,
            report_serializer=cls.report_dict,
            include_all=include_all,
        )

    @classmethod
    async def get_report(
        cls,
        db: AsyncSession,
        user_id: int,
        report_id: str,
        *,
        include_all: bool = False,
    ) -> dict[str, Any]:
        return await ResearchReportService.get_report(
            db,
            user_id,
            report_id,
            report_serializer=cls.report_dict,
            include_all=include_all,
        )

    @staticmethod
    async def export_report(
        db: AsyncSession,
        user_id: int,
        report_id: str,
        *,
        allow_draft: bool = False,
    ) -> dict[str, Any]:
        return await ResearchReportService.export_markdown(
            db,
            user_id,
            report_id,
            allow_draft=allow_draft,
        )

    @staticmethod
    async def export_report_file(
        db: AsyncSession,
        user_id: int,
        report_id: str,
        file_format: str,
        *,
        allow_draft: bool = False,
    ) -> tuple[str, str, bytes]:
        return await ResearchReportService.export_file(
            db,
            user_id,
            report_id,
            file_format,
            allow_draft=allow_draft,
        )

    @staticmethod
    async def create_report_export(
        db: AsyncSession,
        user_id: int,
        report_id: str,
        file_format: str,
        *,
        allow_draft: bool = False,
    ) -> dict[str, Any]:
        return await ResearchReportExportService.create(
            db,
            user_id=user_id,
            report_id=report_id,
            file_format=file_format,
            allow_draft=allow_draft,
        )

    @staticmethod
    async def list_report_exports(db: AsyncSession, user_id: int, report_id: str, *, include_all: bool = False) -> dict[str, Any]:
        return await ResearchReportExportService.list(db, user_id=user_id, report_id=report_id, include_all=include_all)

    @staticmethod
    async def download_report_export(
        db: AsyncSession,
        user_id: int,
        export_id: str,
    ) -> tuple[str, str, bytes]:
        return await ResearchReportExportService.download(db, user_id=user_id, export_id=export_id)

    @classmethod
    async def update_report(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        report_id: str,
        payload: PipelineReportUpdateModel,
    ) -> dict[str, Any]:
        return await ResearchReportService.update_report(
            db,
            user_id=user_id,
            owner_name=owner_name,
            report_id=report_id,
            payload=payload,
            report_serializer=cls.report_dict,
        )

    @staticmethod
    async def get_report_diagram(db: AsyncSession, user_id: int, report_id: str) -> dict[str, Any]:
        return await ResearchReportService.get_diagram(db, user_id, report_id)

    @staticmethod
    async def update_report_diagram(
        db: AsyncSession,
        *,
        user_id: int,
        report_id: str,
        payload: PipelineDiagramUpdateModel,
    ) -> dict[str, Any]:
        return await ResearchReportService.update_diagram(
            db,
            user_id=user_id,
            report_id=report_id,
            payload=payload,
        )

    @classmethod
    async def list_report_versions(cls, db: AsyncSession, user_id: int, report_id: str, *, include_all: bool = False) -> dict[str, Any]:
        return await ResearchReportService.list_versions(
            db,
            user_id,
            report_id,
            date_formatter=cls._datetime_text,
            include_all=include_all,
        )

    @classmethod
    async def get_report_version(
        cls,
        db: AsyncSession,
        user_id: int,
        report_id: str,
        version_no: int,
        *, include_all: bool = False,
    ) -> dict[str, Any]:
        return await ResearchReportService.get_version(
            db,
            user_id,
            report_id,
            version_no,
            date_formatter=cls._datetime_text,
            include_all=include_all,
        )

    @classmethod
    async def restore_report_version(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        report_id: str,
        version_no: int,
    ) -> dict[str, Any]:
        return await ResearchReportService.restore_version(
            db,
            user_id=user_id,
            owner_name=owner_name,
            report_id=report_id,
            version_no=version_no,
            report_serializer=cls.report_dict,
        )
