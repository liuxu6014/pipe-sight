from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.entity.do.pipeline_do import PipelineTemplateVersion


class PipelineTemplateService:
    """管理科研报告与情报简报模板的版本、发布和停用。"""

    _categories = frozenset({'research', 'digest', 'project'})
    _defaults = (
        {
            'template_key': 'template-01', 'code': 'P-01', 'category': 'project', 'report_type': 'project-demand',
            'name': '科技项目需求填报表', 'description': '结构化封面、需求背景、技术指标与经费预算', 'color': '#2764e7',
            'version_label': 'V3.0', 'sections': [
                {'id': 1, 'title': '生产需求及技术问题', 'words': 1800, 'required': True},
                {'id': 2, 'title': '国内外技术现状分析', 'words': 2200, 'required': True},
                {'id': 3, 'title': '研究目标', 'words': 1600, 'required': True},
                {'id': 4, 'title': '研究内容', 'words': 2200, 'required': True},
                {'id': 5, 'title': '预期研究成果', 'words': 1600, 'required': True},
                {'id': 6, 'title': '经费需求', 'words': 1000, 'required': True},
            ],
        },
        {
            'template_key': 'template-02', 'code': 'R-01', 'category': 'research', 'report_type': 'research-demand',
            'name': '科研需求报告', 'description': '问题分析、研究目标、研究内容、考核指标', 'color': '#0b8f87',
            'version_label': 'V2.1', 'sections': [
                {'id': 1, 'title': '问题与必要性', 'words': 1800, 'required': True},
                {'id': 2, 'title': '研究现状与差距', 'words': 2200, 'required': True},
                {'id': 3, 'title': '研究目标', 'words': 1800, 'required': True},
                {'id': 4, 'title': '研究内容与创新点', 'words': 2400, 'required': True},
                {'id': 5, 'title': '考核指标', 'words': 1200, 'required': True},
                {'id': 6, 'title': '预期成果与应用', 'words': 1200, 'required': True},
            ],
        },
        {
            'template_key': 'template-03', 'code': 'R-02', 'category': 'research', 'report_type': 'technology-route',
            'name': '技术路线报告', 'description': '现状评估、技术路线、试验验证与实施计划', 'color': '#7357c8',
            'version_label': 'V1.6', 'sections': [
                {'id': 1, 'title': '需求边界与现状评估', 'words': 1800, 'required': True},
                {'id': 2, 'title': '关键问题', 'words': 1800, 'required': True},
                {'id': 3, 'title': '技术路线与阶段任务', 'words': 2800, 'required': True},
                {'id': 4, 'title': '试验验证方案', 'words': 2200, 'required': True},
                {'id': 5, 'title': '里程碑与阶段成果', 'words': 1400, 'required': True},
                {'id': 6, 'title': '风险与备选方案', 'words': 1000, 'required': True},
            ],
        },
        {
            'template_key': 'daily-v2', 'code': 'D-01', 'category': 'digest', 'report_type': 'daily',
            'name': '管网科技情报日报', 'description': '今日要闻、技术进展、热点研判和来源清单', 'color': '#c26a2e',
            'version_label': 'V2.0', 'sections': [
                {'id': 1, 'title': '今日要闻', 'words': 1200, 'required': True},
                {'id': 2, 'title': '技术进展', 'words': 1200, 'required': True},
                {'id': 3, 'title': '热点研判', 'words': 1000, 'required': False},
                {'id': 4, 'title': '来源清单', 'words': 500, 'required': True},
            ],
        },
        {
            'template_key': 'weekly-v1', 'code': 'D-02', 'category': 'digest', 'report_type': 'weekly',
            'name': '检测技术专题周报', 'description': '面向检测技术主题的周度情报汇总', 'color': '#14845d',
            'version_label': 'V1.5', 'sections': [
                {'id': 1, 'title': '本周要闻', 'words': 1400, 'required': True},
                {'id': 2, 'title': '检测技术动态', 'words': 1600, 'required': True},
                {'id': 3, 'title': '周度趋势研判', 'words': 1200, 'required': False},
                {'id': 4, 'title': '来源清单', 'words': 500, 'required': True},
            ],
        },
        {
            'template_key': 'monthly-v1', 'code': 'D-03', 'category': 'digest', 'report_type': 'monthly',
            'name': '管网科技情报月报', 'description': '月度要闻、趋势变化、风险机会与下月关注', 'color': '#a86f22',
            'version_label': 'V1.0', 'sections': [
                {'id': 1, 'title': '月度要闻', 'words': 1600, 'required': True},
                {'id': 2, 'title': '趋势变化', 'words': 1800, 'required': True},
                {'id': 3, 'title': '风险与机会', 'words': 1400, 'required': False},
                {'id': 4, 'title': '下月关注', 'words': 1000, 'required': False},
                {'id': 5, 'title': '来源清单', 'words': 500, 'required': True},
            ],
        },
    )

    @classmethod
    def _dict(cls, template: PipelineTemplateVersion) -> dict[str, Any]:
        return {
            'id': template.template_id,
            'templateKey': template.template_key,
            'code': template.code,
            'category': template.category,
            'reportType': template.report_type,
            'type': {'research': '科研报告', 'digest': '日报周月报', 'project': '项目填报表'}.get(template.category, template.category),
            'name': template.name,
            'description': template.description,
            'color': template.color,
            'version': template.version_label,
            'versionNo': template.version_no,
            'status': template.status,
            'formats': list(template.formats or []),
            'sections': list(template.sections or []),
            'usage': template.usage_count,
            'operator': template.operator_name,
            'publishedAt': template.published_at.isoformat() if template.published_at else None,
            'updatedAt': template.update_time.isoformat() if template.update_time else None,
        }

    @classmethod
    async def ensure_default_templates(cls, db: Any) -> None:
        existing = await PipelineDao.list_template_versions(db)
        if existing:
            return
        now = datetime.now()
        for item in cls._defaults:
            await PipelineDao.add_template(
                db,
                PipelineTemplateVersion(
                    template_id=f"template-{uuid4().hex[:16]}",
                    version_no=1,
                    status='published',
                    formats=['docx'],
                    usage_count=0,
                    operator_name='系统默认',
                    published_at=now,
                    create_time=now,
                    update_time=now,
                    **item,
                ),
            )

    @classmethod
    async def list_templates(cls, db: Any, category: str | None = None, published_only: bool = False) -> dict[str, Any]:
        rows = await PipelineDao.list_template_versions(db, category=category)
        latest: dict[str, PipelineTemplateVersion] = {}
        for row in rows:
            if published_only and row.status != 'published':
                continue
            latest.setdefault(row.template_key, row)
        return {'rows': [cls._dict(item) for item in latest.values()], 'total': len(latest)}

    @classmethod
    async def get_published(cls, db: Any, template_key: str) -> PipelineTemplateVersion | None:
        return await PipelineDao.get_published_template(db, template_key)

    @classmethod
    async def save_draft(cls, db: Any, *, template_key: str | None, payload: dict[str, Any], operator_id: int, operator_name: str) -> dict[str, Any]:
        category = payload['category']
        if category not in cls._categories:
            raise ServiceException(message='模板分类不合法')
        if not payload['sections']:
            raise ServiceException(message='模板至少需要一个章节')
        key = (template_key or '').strip() or f"custom-{uuid4().hex[:12]}"
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,63}', key):
            raise ServiceException(message='模板编码仅支持小写字母、数字和短横线')
        latest = await PipelineDao.get_latest_template(db, key)
        now = datetime.now()
        template = PipelineTemplateVersion(
            template_id=f'template-{uuid4().hex[:16]}',
            template_key=key,
            version_no=(latest.version_no + 1) if latest else 1,
            status='draft',
            formats=payload['formats'] or ['docx'],
            sections=payload['sections'],
            usage_count=latest.usage_count if latest else 0,
            operator_id=operator_id,
            operator_name=operator_name,
            create_time=now,
            update_time=now,
            **{field: payload[field] for field in ('code', 'category', 'report_type', 'name', 'description', 'color', 'version_label')},
        )
        await PipelineDao.add_template(db, template)
        await db.commit()
        await db.refresh(template)
        return cls._dict(template)

    @classmethod
    async def publish(cls, db: Any, template_key: str, *, operator_id: int, operator_name: str) -> dict[str, Any]:
        latest = await PipelineDao.get_latest_template(db, template_key)
        if not latest:
            raise ServiceException(message='模板不存在')
        if latest.status == 'published':
            return cls._dict(latest)
        if not latest.sections:
            raise ServiceException(message='模板没有章节，不能发布')
        rows = await PipelineDao.list_template_versions(db, template_key=template_key)
        now = datetime.now()
        for row in rows:
            if row.status == 'published':
                row.status = 'retired'
        latest.status = 'published'
        latest.operator_id = operator_id
        latest.operator_name = operator_name
        latest.published_at = now
        latest.update_time = now
        await db.commit()
        await db.refresh(latest)
        return cls._dict(latest)

    @classmethod
    async def retire(cls, db: Any, template_key: str) -> dict[str, Any]:
        latest = await PipelineDao.get_latest_template(db, template_key)
        if not latest:
            raise ServiceException(message='模板不存在')
        latest.status = 'retired'
        latest.update_time = datetime.now()
        await db.commit()
        await db.refresh(latest)
        return cls._dict(latest)
