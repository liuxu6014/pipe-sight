"""论文生成旧接口到统一科研任务服务的兼容适配。"""

from __future__ import annotations

from typing import Any

from app.intelligence.schemas.pipeline import PipelineResearchJobCreateModel
from app.research.services.application import ResearchApplicationService
from exceptions.exception import ServiceException


class ManuscriptApiService:
    """保留论文页面接口，同时复用持久化科研任务和报告流水线。"""

    _REPORT_TYPES = {
        'fund': 'project-demand',
        'key_research': 'research-demand',
        'review': 'technology-route',
    }

    @classmethod
    def to_research_payload(cls, body: Any) -> PipelineResearchJobCreateModel:
        topic = body.topic.strip()
        if not topic:
            raise ServiceException(message='论文题目不能为空')
        custom_options = dict(body.custom_options or {})
        custom_outline = body.custom_outline or {}
        outline = cls._normalize_outline(custom_outline.get('sections'))
        options = {
            **custom_options,
            'manuscript': True,
            'manuscriptTemplateType': body.template_type or 'review',
            'language': body.language or 'zh',
            'visualMode': body.visual_mode or 'direct',
            'manualReferences': cls._clean_list(body.provided_references),
            'manualSections': dict(body.manual_sections or {}),
        }
        return PipelineResearchJobCreateModel(
            title=topic,
            report_type=cls._REPORT_TYPES.get(body.template_type, 'technology-route'),
            template_id=body.template_id,
            direction=topic,
            scenario='管网科研论文',
            keywords=cls._clean_list(body.keywords),
            requirements=(body.description or '').strip(),
            diagram=bool(custom_options.get('generate_figures') or custom_options.get('generateFigures')),
            citation_check=True,
            selected_item_ids=body.selected_item_ids,
            outline=outline,
            options=options,
        )

    @staticmethod
    def _clean_list(values: list[str] | None) -> list[str]:
        return [value.strip() for value in values or [] if str(value).strip()]

    @staticmethod
    def _normalize_outline(sections: Any) -> list[dict[str, Any]]:
        if not isinstance(sections, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in sections:
            if not isinstance(item, dict):
                continue
            title = str(item.get('title') or item.get('heading') or '').strip()
            if not title:
                continue
            normalized.append(
                {
                    'title': title,
                    'level': int(item.get('level') or 1),
                    'words': int(item.get('words') or 0),
                    'description': str(item.get('description') or '').strip(),
                }
            )
        return normalized

    @staticmethod
    def _legacy_job(job: dict[str, Any], report: dict[str, Any] | None = None) -> dict[str, Any]:
        config = dict(job.get('config') or {})
        options = dict(config.get('options') or {})
        report_content = report.get('content', '') if report else ''
        references = list(options.get('manualReferences') or options.get('manual_references') or [])
        return {
            'job_id': job['jobId'],
            'topic': job['title'],
            'description': config.get('requirements', ''),
            'keywords': list(config.get('keywords') or []),
            'provided_references': references,
            'template_type': options.get('manuscriptTemplateType', 'review'),
            'language': options.get('language', 'zh'),
            'visual_mode': options.get('visualMode', 'direct'),
            'status': job['status'],
            'current_stage': job['stage'],
            'progress_pct': job['progress'],
            'created_at': job['createdAt'],
            'updated_at': job['updatedAt'],
            'stages': list(job.get('stages') or []),
            'outline': list(job.get('outline') or []),
            'content': report_content,
            'word_count': len(report_content),
            'report_id': job.get('reportId'),
            'generation_warning': job.get('generationWarning', ''),
            'requires_review': job.get('requiresReview', False),
            'reused': bool(job.get('reused', False)),
        }

    @classmethod
    async def queue(cls, db: Any, user_id: int, owner_name: str, body: Any) -> dict[str, Any]:
        data = await ResearchApplicationService.queue_job(
            db,
            user_id=user_id,
            owner_name=owner_name,
            payload=cls.to_research_payload(body),
        )
        return cls._legacy_job(data)

    @classmethod
    async def list(
        cls,
        db: Any,
        user_id: int,
        keyword: str | None,
        status: str | None,
        page_num: int,
        page_size: int,
    ) -> dict[str, Any]:
        data = await ResearchApplicationService.list_jobs(db, user_id)
        rows = [cls._legacy_job(item) for item in data['rows']]
        if status:
            rows = [item for item in rows if item['status'] == status]
        if keyword and keyword.strip():
            normalized = keyword.strip().lower()
            rows = [
                item
                for item in rows
                if normalized in item['topic'].lower()
                or normalized in item['description'].lower()
                or any(normalized in value.lower() for value in item['keywords'])
            ]
        total = len(rows)
        start = max(page_num - 1, 0) * page_size
        return {'rows': rows[start : start + page_size], 'total': total}

    @classmethod
    async def get(cls, db: Any, user_id: int, job_id: str) -> dict[str, Any]:
        data = await ResearchApplicationService.get_job(db, user_id, job_id)
        report = None
        if data.get('reportId'):
            report = await ResearchApplicationService.get_report(db, user_id, data['reportId'])
        return cls._legacy_job(data, report)

    @classmethod
    async def export(cls, db: Any, user_id: int, job_id: str) -> dict[str, Any]:
        data = await ResearchApplicationService.get_job(db, user_id, job_id)
        report_id = data.get('reportId')
        if not report_id:
            raise ServiceException(message='论文尚未生成报告，请等待后台任务完成')
        return await ResearchApplicationService.export_report(db, user_id, report_id, allow_draft=True)

    @staticmethod
    def suggest_titles(description: str, keywords: list[str] | None = None) -> list[str]:
        normalized_keywords = ManuscriptApiService._clean_list(keywords)
        focus = normalized_keywords[0] if normalized_keywords else ManuscriptApiService._extract_focus(description)
        secondary = normalized_keywords[1] if len(normalized_keywords) > 1 else '管网工程'
        candidates = [
            f'{focus}关键技术及工程应用研究',
            f'面向{secondary}的{focus}方法',
            f'{focus}与{secondary}协同优化综述',
            f'长输管道场景下{focus}评价体系研究',
            f'基于多源数据的{focus}分析方法',
        ]
        return list(dict.fromkeys(candidates))[:5]

    @staticmethod
    def _extract_focus(description: str) -> str:
        text = (description or '').strip()
        for marker in ('研究', '围绕', '面向'):
            if marker in text:
                text = text.split(marker, 1)[-1]
        return text[:16] or '管网技术'
