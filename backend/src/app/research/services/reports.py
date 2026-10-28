"""成果编辑、导出和历史恢复；不依赖审核/发布表。"""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from app.business_ids import parse_business_id, wire_id
from app.business_time import format_business_time
from app.intelligence.models.configuration import PipelineTemplateVersion
from app.research.models.research_models import utcnow
from app.research.repositories.research_repository import ResearchDao
from app.research.services.execution import ResearchExecutionService
from app.research.services.exporters import build_file, safe_file_stem
from app.research.services.report_content import (
    normalize_generated_report, number_report_citations, validate_generated_article,
)
from app.research.services.report_revision import report_revision
from exceptions.exception import ServiceException


class ResearchReportService:
    @staticmethod
    def current_history(report: Any) -> Any:
        history = getattr(report, '_display_history', None)
        if history and (history.report_id != report.id or history.version != report.version
                        or history.title != report.title or history.content != report.content):
            return None
        return history

    @staticmethod
    async def _load_display_history(db: Any, report: Any, *, refresh: bool = False) -> None:
        if refresh:
            await db.refresh(report)
        report._display_history = await ResearchDao.get_report_version(db, report.id, report.version)

    @staticmethod
    async def _live_template_id(db: Any, identity: Any) -> int | None:
        if identity is None:
            return None
        identity = parse_business_id(identity)
        # Keep an extant template from being deleted between validation and FK
        # update. This does not require it to remain enabled or re-run a model.
        return await db.scalar(select(PipelineTemplateVersion.id).where(
            PipelineTemplateVersion.id == identity).with_for_update(read=True, key_share=True))

    @staticmethod
    async def _owned(db, user_id, report_id, lock=False, include_all=False):
        row = await ResearchDao.get_report(db, report_id, None if include_all else user_id, lock=lock)
        if not row:
            raise ServiceException(message='成果不存在或无权访问')
        return row

    @classmethod
    async def list_reports(cls, db, user_id, *, report_serializer, include_all=False):
        rows = await ResearchDao.list_reports(db, user_id)
        for row in rows:
            await cls._load_display_history(db, row)
        return {'rows': [report_serializer(row) for row in rows], 'total': len(rows)}

    @classmethod
    async def get_report(cls, db, user_id, report_id, *, report_serializer, include_all=False):
        row = await cls._owned(db, user_id, report_id, include_all=include_all)
        await cls._load_display_history(db, row)
        return {**report_serializer(row), 'readOnly': str(row.user_id) != str(user_id)}

    @staticmethod
    def _check_version(report, expected_version, expected_revision=None):
        if expected_version is None or expected_version != report.version:
            raise ServiceException(message='成果版本已变化，请刷新后保存')
        if expected_revision and report_revision(report) != expected_revision:
            raise ServiceException(message='成果修订已变化，请刷新后保存')

    @classmethod
    async def update_report(cls, db, *, user_id, owner_name, report_id, payload, report_serializer):
        report = await cls._owned(db, user_id, report_id, lock=True)
        cls._check_version(
            report, getattr(payload, 'expected_version', None), getattr(payload, 'expected_revision', None)
        )
        data = payload.model_dump(exclude_unset=True) if hasattr(payload, 'model_dump') else vars(payload)
        title = data.get('title') if data.get('title') is not None else report.title
        if not str(title).strip():
            raise ServiceException(message='标题不能为空')
        content = data.get('content')
        if content is None and data.get('sections') is not None:
            content = '\n\n'.join(f'## {s.get("title", "")}\n\n{s.get("content", "")}' for s in data['sections'])
        await ResearchExecutionService.save_version(db, report, 'before_edit', user_id, owner_name)
        report.title = title
        if content is not None:
            report.content = content
        report.version += 1
        report.updated_at = utcnow()
        await ResearchExecutionService.save_version(
            db, report, 'manual', user_id, owner_name,
            sections=data.get('sections'), citations=data.get('citations'), quality_issues=data.get('quality_issues'),
        )
        await db.commit()
        await cls._load_display_history(db, report, refresh=True)
        return report_serializer(report)

    @classmethod
    async def _get_export_report(cls, db, user_id, report_id, *, allow_draft=False):
        row = await cls._owned(db, user_id, report_id)
        if not row.content.strip():
            raise ServiceException(message='成果正文为空，不能导出')
        # Transient renderer context, not an ORM/table field. Both synchronous
        # export_snapshot callers (including queued exports) receive real history.
        row._export_history = await ResearchDao.get_report_version(db, row.id, row.version)
        return row, False

    @classmethod
    async def apply_task_result(cls, db, *, user_id, owner_name, job_id, expected_version, report_serializer):
        job = await ResearchDao.get_research_job(db, job_id, user_id, lock=True)
        if not job or job.status != 'completed' or not job.result_content:
            raise ServiceException(message='任务未完成、结果为空或无权访问')
        report = await cls._owned(db, user_id, job.report_id, lock=True)
        cls._check_version(report, expected_version)
        template_id = (job.config_snapshot.get('template') or {}).get('id')
        if template_id is None:
            raise ServiceException(message='任务快照缺少模板信息，不能应用')
        template_id = await cls._live_template_id(db, template_id)
        if template_id is None:
            raise ServiceException(message='任务快照关联模板已不存在，不能应用')
        normalized = normalize_generated_report(job.result_content, job.materials, delivery=True)
        try:
            # Older tasks may contain uncited prose; do not silently repair it,
            # but reject broken markers and incomplete structures on application.
            validate_generated_article(normalized['content'], job.materials, require_citations=False)
        except ValueError as error:
            raise ServiceException(message=str(error)) from None
        await ResearchExecutionService.save_version(db, report, 'before_apply', user_id, owner_name)
        report.content = normalized['content']
        report.template_id = template_id
        report.version += 1
        report.updated_at = utcnow()
        await ResearchExecutionService.save_version(
            db, report, 'applied', user_id, owner_name, job.config_snapshot,
            sections=normalized['sections'], citations=ResearchExecutionService.material_citations(job.materials),
            quality_issues=[],
        )
        await db.commit()
        await cls._load_display_history(db, report, refresh=True)
        return report_serializer(report)

    @classmethod
    async def export_markdown(cls, db, user_id, report_id, *, allow_draft=False):
        report, _ = await cls._get_export_report(db, user_id, report_id, allow_draft=allow_draft)
        filename = safe_file_stem(report.title, is_draft=False) + '.md'
        return {
            'filename': filename,
            'fileName': filename,
            'file_name': filename,
            'content': report.content,
            'isDraft': False,
        }

    @staticmethod
    def export_snapshot(report, history=None):
        # 仅为现有文件渲染器适配 DTO，不是旧 ORM 列。
        history = history if history is not None else getattr(report, '_export_history', None)
        if history and (history.report_id != report.id or history.version != report.version
                        or history.title != report.title or history.content != report.content):
            history = None
        snapshot = deepcopy(history.model_snapshot or {}) if history else {}
        template = snapshot.get('template') or {}
        metadata = {'modelSnapshot': snapshot} if history else {}
        if history:
            metadata.update(source=history.source, operator=history.operator_name,
                            qualityIssues=deepcopy(history.quality_issues or []))
        if template.get('id') is not None:
            metadata['templateId'] = template['id']
            metadata['templateVersion'] = template.get('name') or str(template['id'])
        period = (snapshot.get('request') or {}).get('period')
        if period:
            metadata['period'] = deepcopy(period)
        citations = deepcopy(history.citations or []) if history else []
        sections = deepcopy(history.sections or []) if history else []
        for section in sections:
            section['content'] = number_report_citations(str(section.get('content') or ''), citations)
        return {
            'title': report.title,
            'content': number_report_citations(report.content, citations),
            'version_no': report.version,
            'report_type': report.type,
            'owner_name': '',
            'sections': sections,
            'citations': citations,
            'metadata': metadata,
        }

    @classmethod
    async def export_file(cls, db, user_id, report_id, file_format, *, allow_draft=False):
        report, _ = await cls._get_export_report(db, user_id, report_id, allow_draft=allow_draft)
        return build_file(SimpleNamespace(**cls.export_snapshot(report)), file_format, is_draft=False)

    @classmethod
    async def list_versions(cls, db, user_id, report_id, *, date_formatter=None, include_all=False):
        await cls._owned(db, user_id, report_id, include_all=include_all)
        rows = await ResearchDao.list_report_versions(db, report_id)
        return {'rows': [cls.version_dict(row) for row in rows], 'total': len(rows)}

    @staticmethod
    def version_dict(row):
        return {
            'id': wire_id(row.id),
            'reportId': wire_id(row.report_id),
            'versionNo': row.version,
            'version': row.version,
            'title': row.title,
            'content': row.content,
            'source': row.source,
            'sections': row.sections or [],
            'citations': row.citations or [],
            'qualityIssues': row.quality_issues or [],
            'operator': row.operator_name,
            'createdAt': format_business_time(row.created_at),
        }

    @classmethod
    async def get_version(cls, db, user_id, report_id, version_no, *, date_formatter=None, include_all=False):
        await cls._owned(db, user_id, report_id, include_all=include_all)
        row = await ResearchDao.get_report_version(db, report_id, version_no)
        if not row:
            raise ServiceException(message='历史版本不存在')
        return cls.version_dict(row)

    @classmethod
    async def restore_version(
        cls, db, *, user_id, owner_name, report_id, version_no, report_serializer, expected_version=None
    ):
        report = await cls._owned(db, user_id, report_id, lock=True)
        if expected_version is not None:
            cls._check_version(report, expected_version)
        old = await ResearchDao.get_report_version(db, report_id, version_no)
        if not old:
            raise ServiceException(message='历史版本不存在')
        template_id = ((old.model_snapshot or {}).get('template') or {}).get('id')
        template_id = await cls._live_template_id(db, template_id)
        await ResearchExecutionService.save_version(db, report, 'before_restore', user_id, owner_name)
        report.title, report.content = old.title, old.content
        # Unknown legacy provenance stays unknown rather than claiming the
        # current template generated a historical body.
        report.template_id = template_id
        report.version += 1
        report.updated_at = utcnow()
        await ResearchExecutionService.save_version(
            db, report, 'restored', user_id, owner_name, old.model_snapshot,
            sections=old.sections, citations=old.citations, quality_issues=old.quality_issues,
        )
        await db.commit()
        await cls._load_display_history(db, report, refresh=True)
        return report_serializer(report)

    @classmethod
    async def get_diagram(cls, db, user_id, report_id):
        await cls._owned(db, user_id, report_id)
        rows = await ResearchDao.list_assets(db, report_id, 'image')
        return {
            'reportId': wire_id(report_id),
            'images': [
                {
                    'id': wire_id(r.id),
                    'status': r.status,
                    'position': r.position,
                    'url': f'/pipeline/research/assets/{r.id}/download' if r.status == 'completed' else '',
                    'error': r.error or '',
                }
                for r in rows
            ],
        }

    @classmethod
    async def update_diagram(cls, db, *, user_id, report_id, payload):
        await cls._owned(db, user_id, report_id)
        raise ServiceException(message='请使用图片资源独立重试接口；旧图形占位数据不再保存')
