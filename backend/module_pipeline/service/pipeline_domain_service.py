from __future__ import annotations

import re
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from uuid import uuid4
from xml.etree import ElementTree as ET

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy import func, select, update

from config.database import AsyncSessionLocal
from config.env import UploadConfig
from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.entity.do.pipeline_do import (
    PipelineArticle,
    PipelineCrawlRun,
    PipelineMaterial,
    PipelinePaper,
    PipelineReport,
    PipelineReportVersion,
    PipelineResearchJob,
    PipelineSource,
    PipelineWorkspaceItem,
)
from module_pipeline.entity.vo.pipeline_vo import (
    PipelineDiagramUpdateModel,
    PipelineReportUpdateModel,
    PipelineResearchJobCreateModel,
    PipelineWorkspaceItemMutationModel,
)
from module_pipeline.integration.insighthub_adapter import InsightHubAdapter
from module_pipeline.service.pipeline_collection_service import PipelineCollectionService
from module_pipeline.service.pipeline_template_service import PipelineTemplateService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PipelineDomainService:
    """管网平台可持久化业务服务。

    当前实现采用“模板 + 证据”生成模式，不依赖外部模型密钥。后续模型网关只需替换
    ``_build_section_content``，任务、版本、引用和权限模型无需重做。
    """

    _stage_labels = [
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
    _permission_labels = {
        'private': '仅自己可见',
        'public': '公开',
    }
    _parse_labels = {'queued': '等待解析', 'indexed': '已解析', 'failed': '解析失败'}
    _permission_scopes = frozenset(_permission_labels)
    _local_parser_extensions = frozenset({'.txt', '.md', '.docx', '.pdf'})
    _external_parser_extensions = frozenset({'.pdf', '.doc'})
    _max_source_bytes = 16 * 1024 * 1024
    _max_extracted_chars = 2_000_000
    _minimum_section_sources = 2

    @classmethod
    async def get_dashboard_summary(cls, db: AsyncSession) -> dict[str, Any]:
        """返回数据库实时汇总，不再使用静态演示指标。"""
        article_count = int(
            (await db.execute(select(func.count(PipelineArticle.article_id)).where(PipelineArticle.review_status != 'rejected'))).scalar_one()
        )
        paper_count = int(
            (await db.execute(select(func.count(PipelinePaper.paper_id)).where(PipelinePaper.review_status != 'rejected'))).scalar_one()
        )
        pending_count = int(
            (
                await db.execute(
                    select(func.count(PipelineArticle.article_id)).where(PipelineArticle.review_status == 'pending')
                )
            ).scalar_one()
        )
        pending_count += int(
            (
                await db.execute(select(func.count(PipelinePaper.paper_id)).where(PipelinePaper.review_status == 'pending'))
            ).scalar_one()
        )
        indexed_material_count = int(
            (
                await db.execute(
                    select(func.count(PipelineMaterial.file_id)).where(PipelineMaterial.parse_status == 'indexed')
                )
            ).scalar_one()
        )

        tasks = await cls.list_collection_tasks(db)
        collect_status = [
            {
                'name': item['source'],
                'status': {'queued': 'running', 'running': 'running', 'failed': 'warning'}.get(item['status'], item['status']),
                'value': item['progress'],
            }
            for item in tasks['rows']
        ]

        articles = await PipelineDao.list_articles(db)
        papers = await PipelineDao.list_papers(db)
        topic_counts = Counter(
            tag
            for item in [*articles, *papers]
            for tag in (item.tags or (item.keywords if isinstance(item, PipelinePaper) else []) or [])
            if tag
        )
        hot_topics = [
            {'name': name, 'heat': min(98, 55 + count * 9), 'count': count}
            for name, count in topic_counts.most_common(6)
        ]

        pending_items = [
            {
                'title': item.title,
                'type': '资讯审核',
                'owner': item.source_name or '公开来源',
                'coverage': 1,
                'status': 'reviewing',
                'updated_at': cls._datetime_text(item.update_time),
            }
            for item in [*articles, *papers]
            if item.review_status == 'pending'
        ][:10]
        return {
            'metrics': [
                {'label': '有效资讯', 'value': article_count, 'unit': '条', 'trend': 'stable'},
                {'label': '待审核', 'value': pending_count, 'unit': '条', 'trend': 'stable'},
                {'label': '论文资料', 'value': paper_count, 'unit': '篇', 'trend': 'stable'},
                {'label': '已解析资料', 'value': indexed_material_count, 'unit': '份', 'trend': 'stable'},
            ],
            'collect_status': collect_status,
            'hot_topics': hot_topics,
            'pending_reviews': pending_items,
        }

    @classmethod
    def _now_text(cls) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @classmethod
    def _datetime_text(cls, value: datetime | None) -> str:
        return value.strftime('%Y-%m-%d %H:%M:%S') if value else ''

    @classmethod
    def _source_dict(cls, item: PipelineSource) -> dict[str, Any]:
        total = item.success_count + item.failure_count
        success_rate = round(item.success_count / total * 100) if total else 0
        return {
            'id': item.source_id,
            'name': item.name,
            'type': item.source_type,
            'frequency': item.schedule_cron or '手动',
            'status': 'enabled' if item.enabled and item.status == 'active' else 'disabled',
            'last_run_time': cls._datetime_text(item.last_run_time),
            'success_rate': success_rate,
            'source_code': getattr(item, 'source_code', ''),
            'endpoint': getattr(item, 'endpoint', None) or '',
            'adapter_key': getattr(item, 'adapter_key', ''),
            'schedule_cron': getattr(item, 'schedule_cron', None) or '',
            'enabled': bool(item.enabled and item.status == 'active'),
            'config_json': getattr(item, 'config_json', None) or {},
            'handoff_mode': getattr(item, 'handoff_mode', 'external'),
            'processor_source_code': getattr(item, 'processor_source_code', None) or '',
        }

    @classmethod
    async def save_source(  # noqa: PLR0913
        cls,
        db: AsyncSession,
        *,
        source_id: str | None,
        source_code: str,
        name: str,
        source_type: str,
        endpoint: str,
        adapter_key: str,
        schedule_cron: str,
        enabled: bool,
        config_json: dict[str, Any],
        handoff_mode: str,
        processor_source_code: str,
        owner_id: int | None,
    ) -> dict[str, Any]:
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{1,99}', source_code):
            raise ServiceException(message='数据源编码仅支持小写字母、数字、短横线和下划线')
        if endpoint:
            parsed = urlparse(endpoint)
            if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
                raise ServiceException(message='数据源入口地址必须是有效的 HTTP 或 HTTPS 地址')
        if adapter_key not in {'pipechina_group_news', 'crossref_works'}:
            raise ServiceException(message='当前版本暂不支持该采集适配器')
        if adapter_key == 'pipechina_group_news' and source_type not in {'news', 'wechat'}:
            raise ServiceException(message='国家管网资讯适配器只能用于新闻源或公众号')
        if adapter_key == 'crossref_works' and source_type != 'paper':
            raise ServiceException(message='Crossref 适配器只能用于论文库')

        existing = await PipelineDao.get_source(db, source_id) if source_id else None
        duplicate = await PipelineDao.get_source_by_code(db, source_code)
        if duplicate and (not existing or duplicate.source_id != existing.source_id):
            raise ServiceException(message='数据源编码已存在，请更换编码')
        now = datetime.now()
        if existing:
            existing.source_code = source_code
            existing.name = name
            existing.source_type = source_type
            existing.endpoint = endpoint or None
            existing.adapter_key = adapter_key
            existing.schedule_cron = schedule_cron or None
            existing.enabled = enabled
            existing.status = 'active' if enabled else 'inactive'
            existing.config_json = config_json or {}
            existing.handoff_mode = handoff_mode
            existing.processor_source_code = processor_source_code or None
            existing.owner_id = owner_id
            existing.update_time = now
            source = existing
        else:
            source = PipelineSource(
                source_id=f'source-{uuid4().hex[:16]}',
                source_code=source_code,
                name=name,
                source_type=source_type,
                endpoint=endpoint or None,
                adapter_key=adapter_key,
                schedule_cron=schedule_cron or None,
                status='active' if enabled else 'inactive',
                enabled=enabled,
                config_json=config_json or {},
                handoff_mode=handoff_mode,
                processor_source_code=processor_source_code or None,
                owner_id=owner_id,
                success_count=0,
                failure_count=0,
                consecutive_failures=0,
                create_time=now,
                update_time=now,
            )
            await PipelineDao.add_source(db, source)
        await db.commit()
        await db.refresh(source)
        return cls._source_dict(source)

    @classmethod
    async def set_source_enabled(cls, db: AsyncSession, source_id: str, enabled: bool) -> dict[str, Any]:
        source = await PipelineDao.get_source(db, source_id)
        if not source:
            raise ServiceException(message='数据源不存在')
        source.enabled = enabled
        source.status = 'active' if enabled else 'inactive'
        source.update_time = datetime.now()
        await db.commit()
        await db.refresh(source)
        return cls._source_dict(source)

    @classmethod
    async def list_sources(cls, db: AsyncSession) -> dict[str, Any]:
        rows = await PipelineDao.list_sources(db)
        return {'rows': [cls._source_dict(item) for item in rows], 'total': len(rows)}

    @classmethod
    async def list_collection_tasks(cls, db: AsyncSession) -> dict[str, Any]:
        sources = await PipelineDao.list_sources(db)
        runs = await PipelineDao.list_collection_runs(db)
        latest_runs: dict[str, PipelineCrawlRun] = {}
        for run in runs:
            latest_runs.setdefault(run.source_id, run)
        rows = []
        for source in sources:
            latest = latest_runs.get(source.source_id)
            status = latest.status if latest else 'waiting'
            progress = 100 if status == 'success' else 0
            if status == 'running':
                progress = 50
            rows.append(
                {
                    'id': source.source_id,
                    'latest_run_id': latest.run_id if latest else '',
                    'name': f'{source.name}采集',
                    'source': source.name,
                    'status': status,
                    'progress': progress,
                    'handoff_status': latest.handoff_status if latest else 'pending',
                    'handoff_count': latest.handoff_count if latest else 0,
                    'handoff_processed_count': latest.handoff_processed_count if latest else 0,
                    'handoff_failed_count': latest.handoff_failed_count if latest else 0,
                    'handoff_progress': (
                        round(latest.handoff_processed_count / latest.handoff_count * 100)
                        if latest and latest.handoff_count
                        else 0
                    ),
                    'latest_message': (
                        latest.error_message
                        if latest and latest.error_message
                        else f'最近运行状态：{status}' if latest else '尚未执行采集'
                    ),
                    'next_run_time': source.schedule_cron or '手动触发',
                }
            )
        return {'rows': rows, 'total': len(rows)}

    @classmethod
    async def queue_collection_run(cls, db: AsyncSession, source_id: str) -> dict[str, Any]:
        source = await PipelineDao.get_source(db, source_id)
        if not source:
            raise ServiceException(message='数据源不存在')
        if not source.enabled or source.status != 'active':
            raise ServiceException(message='数据源已停用，不能执行采集')
        if getattr(source, 'adapter_key', None) in {'pipechina_group_news', 'crossref_works'}:
            result = await PipelineCollectionService.collect_source(db, source)
            return {
                'id': source.source_id,
                'name': f'{source.name}采集',
                'source': source.name,
                'status': result['status'],
                'progress': 100 if result['status'] == 'success' else 0,
                'latest_message': (
                    f"本轮抓取 {result['fetched']} 条，新增 {result['inserted']} 条，"
                    f"更新 {result['updated']} 条，重复 {result['duplicates']} 条"
                ),
                'next_run_time': source.schedule_cron or '手动触发',
            }
        now = datetime.now()
        run = PipelineCrawlRun(
            run_id=f'run-{uuid4().hex[:16]}',
            source_id=source.source_id,
            trigger_type='manual',
            status='queued',
            config_snapshot=dict(source.config_json or {}),
            checkpoint_json={},
            create_time=now,
            update_time=now,
        )
        source.last_run_time = now
        source.last_run_status = 'queued'
        source.update_time = now
        await PipelineDao.add_collection_run(db, run)
        await db.commit()
        return {
            'id': source.source_id,
            'name': f'{source.name}采集',
            'source': source.name,
            'status': 'queued',
            'progress': 0,
            'latest_message': '已创建手动采集运行，等待采集执行器处理',
            'next_run_time': source.schedule_cron or '手动触发',
        }

    @classmethod
    async def dispatch_insighthub_handoff(
        cls,
        db: AsyncSession,
        run_id: str,
        *,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Submit collected articles to InsightHub and persist the dispatch receipt."""
        run = await PipelineDao.get_collection_run(db, run_id)
        if not run:
            raise ServiceException(message='采集运行不存在')
        source = await PipelineDao.get_source(db, run.source_id)
        if not source:
            raise ServiceException(message='采集运行的数据源不存在')
        if source.handoff_mode != 'external':
            raise ServiceException(message='该数据源未启用外部处理')
        articles = await PipelineDao.list_handoff_articles(db, run_id=run_id, limit=limit)
        if not articles:
            return {'run_id': run_id, 'handoff_count': 0, 'handoff_status': run.handoff_status}

        try:
            receipts = await InsightHubAdapter().submit_articles(source, list(articles))
        except Exception as exc:
            run.handoff_status = 'failed'
            run.handoff_error = str(exc)[:2000]
            run.handoff_time = datetime.now()
            await db.commit()
            raise ServiceException(message='外部处理系统提交失败，请检查连接和权限') from exc

        receipt_by_article = {item['article_id']: item for item in receipts}
        for article in articles:
            receipt = receipt_by_article.get(article.article_id)
            if not receipt:
                continue
            article.handoff_status = receipt['handoff_status']
            article.handoff_batch_id = run_id
            article.handoff_record_id = receipt['handoff_record_id']
            article.handoff_result_json = {
                'handoff_create_time': cls._datetime_text(receipt.get('handoff_create_time')),
            }
            article.handoff_time = datetime.now()
            article.handoff_error = None

        completed_count = sum(item['handoff_status'] == 'completed' for item in receipts)
        run.handoff_status = 'completed' if receipts and completed_count == len(receipts) else 'dispatched'
        run.handoff_batch_id = run_id
        run.handoff_count = len(receipts)
        run.handoff_processed_count = completed_count
        run.handoff_failed_count = 0
        run.handoff_time = datetime.now()
        run.handoff_error = None
        await db.commit()
        return {
            'run_id': run_id,
            'handoff_batch_id': run_id,
            'handoff_count': len(receipts),
            'handoff_status': run.handoff_status,
        }

    @classmethod
    async def sync_insighthub_handoff(
        cls,
        db: AsyncSession,
        run_id: str,
        *,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Poll InsightHub and update PipeSight's raw handoff snapshots."""
        run = await PipelineDao.get_collection_run(db, run_id)
        if not run:
            raise ServiceException(message='采集运行不存在')
        articles = await PipelineDao.list_handoff_articles(
            db, run_id=run_id, limit=limit, include_completed=True
        )
        article_ids = [item.article_id for item in articles if item.handoff_record_id]
        if not article_ids:
            return {'run_id': run_id, 'processed_count': 0, 'failed_count': 0, 'handoff_status': run.handoff_status}

        try:
            results = await InsightHubAdapter().fetch_processing_results(article_ids)
        except Exception as exc:
            raise ServiceException(message='外部处理结果同步失败，请检查连接和权限') from exc
        processed = failed = 0
        for article in articles:
            result = results.get(article.article_id)
            if not result:
                continue
            status = result['status']
            article.handoff_status = status
            article.handoff_record_id = str(result['news_id'])
            article.handoff_trace_id = result.get('prompt_trace_id')
            article.handoff_result_json = dict(result.get('result') or {})
            article.handoff_time = datetime.now()
            article.handoff_error = None
            if status == 'completed':
                processed += 1
            elif status == 'rejected':
                failed += 1

        total = len(article_ids)
        run.handoff_processed_count = processed
        run.handoff_failed_count = failed
        run.handoff_time = datetime.now()
        if processed == total:
            run.handoff_status = 'completed'
        elif failed and processed:
            run.handoff_status = 'partial'
        elif failed == total:
            run.handoff_status = 'failed'
        else:
            run.handoff_status = 'processing'
        await db.commit()
        return {
            'run_id': run_id,
            'processed_count': processed,
            'failed_count': failed,
            'pending_count': max(total - processed - failed, 0),
            'handoff_status': run.handoff_status,
        }

    @classmethod
    def _article_dict(cls, item: PipelineArticle, *, detail: bool = False) -> dict[str, Any]:
        data = {
            'id': item.article_id,
            'category': item.article_type,
            'title': item.title,
            'source': item.source_name or '未知来源',
            'source_type': item.article_type,
            'publish_time': cls._datetime_text(item.published_time),
            'relevance': item.relevance_score,
            'status': item.review_status,
            'tags': list(item.tags or []),
            'summary': item.summary or '',
            'source_url': item.canonical_url or '',
            'sourceUrl': item.canonical_url or '',
            'processing_status': item.handoff_status,
            'processing_version': item.handoff_version or '',
        }
        if detail:
            data.update(
                {
                    'content': item.body or item.summary or '',
                    'related_topics': list(item.tags or []),
                    'entities': list((item.metadata_json or {}).get('entities') or []),
                    'timeline': list((item.metadata_json or {}).get('timeline') or []),
                    'processing_result': dict(item.handoff_result_json or {}),
                }
            )
        return data

    @classmethod
    def _paper_dict(cls, item: PipelinePaper, *, detail: bool = False) -> dict[str, Any]:
        metadata = dict(item.metadata_json or {})
        data = {
            'id': item.paper_id,
            'category': 'paper',
            'title': item.title,
            'source': item.source_name or item.journal or '论文数据库',
            'source_type': 'paper',
            'publish_time': str(item.publication_year or ''),
            'relevance': int(metadata.get('relevanceScore') or 0),
            'status': item.review_status,
            'tags': list(item.tags or item.keywords or []),
            'summary': item.abstract_text or '',
            'source_url': item.canonical_url or '',
            'sourceUrl': item.canonical_url or '',
            'doi': item.doi or '',
            'authors': list(item.authors_json or []),
            'journal': item.journal or '',
            'citation_count': int(item.citation_count or 0),
            'open_access_status': item.open_access_status or 'unknown',
            'processing_status': item.handoff_status,
            'processing_version': item.handoff_version or '',
        }
        if detail:
            data.update(
                {
                    'content': item.abstract_text or '',
                    'related_topics': list(item.tags or item.keywords or []),
                    'entities': list(metadata.get('entities') or []),
                    'timeline': list(metadata.get('timeline') or []),
                    'processing_result': dict(item.handoff_result_json or {}),
                }
            )
        return data

    @classmethod
    async def list_intelligence(
        cls,
        db: AsyncSession,
        *,
        category: str | None,
        keyword: str | None,
        source_type: str | None,
        page_num: int,
        page_size: int,
    ) -> dict[str, Any]:
        include_articles = category != 'paper' and source_type != 'paper'
        include_papers = category in {None, 'paper'} and source_type in {None, 'paper'}
        article_type = category if category in {'news', 'wechat'} else None
        if source_type in {'news', 'wechat'}:
            article_type = source_type
        rows: list[dict[str, Any]] = []
        if include_articles:
            rows.extend(
                cls._article_dict(item)
                for item in await PipelineDao.list_articles(db, article_type=article_type, keyword=keyword)
                if getattr(item, 'review_status', 'approved') == 'approved'
            )
        if include_papers:
            rows.extend(
                cls._paper_dict(item)
                for item in await PipelineDao.list_papers(db, keyword=keyword)
                if getattr(item, 'review_status', 'approved') == 'approved'
            )
        rows.sort(key=lambda item: item['publish_time'], reverse=True)
        total = len(rows)
        start = (page_num - 1) * page_size
        return {'rows': rows[start : start + page_size], 'total': total}

    @classmethod
    async def get_intelligence_detail(cls, db: AsyncSession, item_id: str) -> dict[str, Any]:
        article = await PipelineDao.get_article(db, item_id)
        if article:
            if getattr(article, 'review_status', 'approved') != 'approved':
                raise ServiceException(message='情报资料不存在或暂不可见')
            return cls._article_dict(article, detail=True)
        paper = await PipelineDao.get_paper(db, item_id)
        if paper:
            if getattr(paper, 'review_status', 'approved') != 'approved':
                raise ServiceException(message='情报资料不存在或暂不可见')
            return cls._paper_dict(paper, detail=True)
        raise ServiceException(message='情报资料不存在')

    @classmethod
    def _material_dict(cls, item: PipelineMaterial, viewer_user_id: int | None = None) -> dict[str, Any]:
        suffix = Path(item.name).suffix.lstrip('.').upper()
        return {
            'id': item.file_id,
            'name': item.name,
            'type': item.category,
            'format': suffix or 'FILE',
            'fileName': item.file_name,
            'fileSize': item.file_size,
            'permissionScope': item.permission_scope,
            'permission': cls._permission_labels.get(item.permission_scope, item.permission_scope),
            'parseStatus': item.parse_status,
            'status': cls._parse_labels.get(item.parse_status, item.parse_status),
            'parseMessage': item.parse_message,
            'allowDownload': bool(getattr(item, 'allow_download', True)),
            'allowAiUse': bool(getattr(item, 'allow_ai_use', True)),
            'contentLevel': '全文可用' if item.parse_status == 'indexed' and item.extracted_text else '摘要或元数据',
            'summary': item.summary or '等待补充资料摘要',
            'tags': list(item.tags or []),
            'keywords': list(item.tags or []),
            'owner': item.owner_name,
            'ownerId': item.owner_id,
            'canManage': viewer_user_id is None or item.owner_id == viewer_user_id,
            'version': f'V{item.version_no}.0',
            'createdAt': cls._datetime_text(item.create_time),
            'updatedAt': cls._datetime_text(item.update_time),
            'updated_at': cls._datetime_text(item.update_time),
            'metadata': dict(item.metadata_json or {}),
        }

    @classmethod
    def _material_detail_dict(cls, item: PipelineMaterial, viewer_user_id: int) -> dict[str, Any]:
        data = cls._material_dict(item, viewer_user_id)
        extracted_text = item.extracted_text or ''
        data.update(
            {
                'extractedText': extracted_text,
                'contentLength': len(extracted_text),
                'hasExtractedText': bool(extracted_text),
            }
        )
        return data

    @classmethod
    async def list_materials(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        rows = await PipelineDao.list_accessible_materials(db, user_id)
        return {'rows': [cls._material_dict(item, user_id) for item in rows], 'total': len(rows)}

    @classmethod
    async def get_material(
        cls,
        db: AsyncSession,
        user_id: int,
        material_id: str,
    ) -> dict[str, Any]:
        material = await PipelineDao.get_accessible_material(db, material_id, user_id)
        if not material:
            raise ServiceException(message='资料不存在或无权访问')
        return cls._material_detail_dict(material, user_id)

    @classmethod
    async def get_material_download(
        cls,
        db: AsyncSession,
        user_id: int,
        material_id: str,
    ) -> tuple[Path, str, str | None]:
        material = await PipelineDao.get_accessible_material(db, material_id, user_id)
        if not material:
            raise ServiceException(message='资料不存在或无权访问')
        if not getattr(material, 'allow_download', True):
            raise ServiceException(message='当前资料禁止下载')
        path = cls._material_local_path(material.file_path)
        if not path or not path.is_file():
            raise ServiceException(message='资料文件不存在或已失效')
        return path, material.name, getattr(material, 'mime_type', None)

    @classmethod
    async def create_material(  # noqa: PLR0913
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        name: str,
        category: str,
        permission_scope: str,
        file_name: str | None,
        file_path: str | None,
        file_url: str | None,
        mime_type: str | None,
        file_size: int,
        local_path: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        permission_scope = permission_scope or 'private'
        if permission_scope not in cls._permission_scopes:
            raise ServiceException(message='资料可见范围不合法')
        parse_status, parse_message, extracted_text, parse_metadata = cls._parse_material_file(local_path, name)
        summary = (
            cls._summarize_text(extracted_text) if extracted_text else f'{category or "内部文献"}资料，{parse_message}'
        )
        material = PipelineMaterial(
            file_id=f'doc-{uuid4().hex[:16]}',
            name=name,
            category=category or '内部文献',
            file_name=file_name,
            file_path=file_path,
            file_url=file_url,
            mime_type=mime_type,
            file_size=max(int(file_size or 0), 0),
            permission_scope=permission_scope,
            parse_status=parse_status,
            parse_message=parse_message,
            summary=summary,
            extracted_text=extracted_text,
            tags=tags or [],
            metadata_json={
                **parse_metadata,
                'parseAttempts': 1 if Path(name).suffix.lower() in cls._local_parser_extensions else 0,
            },
            owner_id=user_id,
            owner_name=owner_name,
        )
        try:
            await PipelineDao.add_material(db, material)
            await db.commit()
            await db.refresh(material)
            return cls._material_detail_dict(material, user_id)
        except Exception:
            await db.rollback()
            raise

    @classmethod
    def extract_plain_text(cls, local_path: str | None, original_name: str) -> str:
        if not local_path:
            return ''
        suffix = Path(original_name).suffix.lower()
        try:
            if suffix in {'.txt', '.md'}:
                return cls._extract_text_file(Path(local_path))
            if suffix == '.docx':
                return cls._extract_docx_text(Path(local_path))
            if suffix == '.pdf':
                return cls._extract_pdf_text(Path(local_path))
        except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError, KeyError, PyPdfError):
            return ''
        return ''

    @classmethod
    def _extract_text_file(cls, source: Path) -> str:
        with source.open('rb') as source_file:
            raw = source_file.read(cls._max_source_bytes + 1)
        raw = raw[: cls._max_source_bytes]
        encodings = (
            ['utf-8-sig', 'utf-16']
            if raw.startswith((b'\xef\xbb\xbf', b'\xff\xfe', b'\xfe\xff'))
            else ['utf-8', 'gb18030']
        )
        for encoding in encodings:
            try:
                return raw.decode(encoding).strip()[: cls._max_extracted_chars]
            except UnicodeDecodeError:  # noqa: PERF203
                continue
        return raw.decode('utf-8', errors='replace').strip()[: cls._max_extracted_chars]

    @classmethod
    def _extract_docx_text(cls, source: Path) -> str:
        word_namespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        paragraph_tag = f'{{{word_namespace}}}p'
        text_tag = f'{{{word_namespace}}}t'
        tab_tag = f'{{{word_namespace}}}tab'
        break_tags = {f'{{{word_namespace}}}br', f'{{{word_namespace}}}cr'}
        with zipfile.ZipFile(source) as archive:
            document_info = archive.getinfo('word/document.xml')
            if document_info.file_size > cls._max_source_bytes:
                raise ValueError('DOCX document.xml exceeds the local parser limit')
            document_root = ET.fromstring(archive.read(document_info))

        paragraphs: list[str] = []
        extracted_chars = 0
        for paragraph in document_root.iter(paragraph_tag):
            fragments: list[str] = []
            for node in paragraph.iter():
                if node.tag == text_tag and node.text:
                    fragments.append(node.text)
                elif node.tag == tab_tag:
                    fragments.append('\t')
                elif node.tag in break_tags:
                    fragments.append('\n')
            paragraph_text = ''.join(fragments).strip()
            if not paragraph_text:
                continue
            remaining = cls._max_extracted_chars - extracted_chars
            if remaining <= 0:
                break
            paragraphs.append(paragraph_text[:remaining])
            extracted_chars += min(len(paragraph_text), remaining) + 1
        return '\n'.join(paragraphs).strip()

    @classmethod
    def _extract_pdf_text(cls, source: Path) -> str:
        if source.stat().st_size > cls._max_source_bytes:
            raise ValueError('PDF exceeds the local parser limit')
        reader = PdfReader(str(source))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('encrypted PDF requires a password')
        pages: list[str] = []
        extracted_chars = 0
        for page in reader.pages:
            page_text = (page.extract_text() or '').strip()
            if not page_text:
                continue
            remaining = cls._max_extracted_chars - extracted_chars
            if remaining <= 0:
                break
            pages.append(page_text[:remaining])
            extracted_chars += min(len(page_text), remaining) + 2
        return '\n\n'.join(pages).strip()

    @classmethod
    def _parse_material_file(
        cls,
        local_path: str | None,
        original_name: str,
    ) -> tuple[str, str, str, dict[str, Any]]:
        suffix = Path(original_name).suffix.lower()
        requested_at = cls._now_text()
        if suffix == '.doc':
            return (
                'failed',
                '暂不支持旧版 DOC，请先另存为 DOCX 或 PDF 后重新上传。',
                '',
                {'parser': 'unsupported-doc', 'lastParseAt': requested_at},
            )
        if suffix not in cls._local_parser_extensions:
            return (
                'queued',
                '文件已安全保存，当前文件类型需要外部解析器处理。',
                '',
                {'parser': 'queued-external-parser', 'lastParseRequestedAt': requested_at},
            )
        if not local_path or not Path(local_path).is_file():
            return (
                'failed',
                '源文件不存在，无法执行基础文本解析。',
                '',
                {'parser': 'local-basic-parser', 'lastParseAt': requested_at},
            )

        extracted_text = cls.extract_plain_text(local_path, original_name)
        parser = {'.docx': 'docx-ooxml', '.pdf': 'pypdf'}.get(suffix, 'plain-text')
        if not extracted_text:
            empty_message = (
                'PDF 未提取到可检索文字，文件可能为扫描版、已加密或已损坏；请转换为可搜索 PDF 或 DOCX 后重试。'
                if suffix == '.pdf'
                else '基础解析未提取到有效正文，请检查文件内容后重试。'
            )
            return (
                'failed',
                empty_message,
                '',
                {'parser': parser, 'lastParseAt': requested_at, 'contentLength': 0},
            )
        truncated = len(extracted_text) >= cls._max_extracted_chars
        message = (
            'PDF 已完成文本提取，可用于关键词检索。' if suffix == '.pdf' else '文本已完成基础提取，可用于关键词检索。'
        )
        if truncated:
            message = f'{message}正文超过本地解析上限，已保留前 {cls._max_extracted_chars} 个字符。'
        return (
            'indexed',
            message,
            extracted_text,
            {
                'parser': parser,
                'lastParseAt': requested_at,
                'contentLength': len(extracted_text),
                'truncated': truncated,
            },
        )

    @classmethod
    def _material_local_path(cls, file_path: str | None) -> Path | None:
        if not file_path:
            return None
        upload_root = Path(UploadConfig.UPLOAD_PATH).resolve()
        normalized = file_path.replace('\\', '/')
        prefix = UploadConfig.UPLOAD_PREFIX.rstrip('/')
        if normalized == prefix or normalized.startswith(f'{prefix}/'):
            candidate = upload_root / normalized[len(prefix) :].lstrip('/')
        else:
            candidate = Path(file_path)
        resolved = candidate.resolve()
        try:
            resolved.relative_to(upload_root)
        except ValueError:
            return None
        return resolved

    @classmethod
    async def retry_material_parse(
        cls,
        db: AsyncSession,
        user_id: int,
        material_id: str,
    ) -> dict[str, Any]:
        material = await PipelineDao.get_owned_material(db, material_id, user_id)
        if not material:
            raise ServiceException(message='资料不存在或无权重新解析')

        local_path = cls._material_local_path(material.file_path)
        parse_status, parse_message, extracted_text, parse_metadata = cls._parse_material_file(
            str(local_path) if local_path else None,
            material.name,
        )
        metadata = dict(material.metadata_json or {})
        metadata.update(parse_metadata)
        metadata['parseAttempts'] = int(metadata.get('parseAttempts') or 0) + 1
        material.parse_status = parse_status
        material.parse_message = parse_message
        material.extracted_text = extracted_text
        material.summary = (
            cls._summarize_text(extracted_text) if extracted_text else f'{material.category}资料，{parse_message}'
        )
        material.metadata_json = metadata
        material.update_time = datetime.now()
        try:
            await db.commit()
            await db.refresh(material)
            return cls._material_detail_dict(material, user_id)
        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def delete_material(
        cls,
        db: AsyncSession,
        user_id: int,
        material_id: str,
    ) -> dict[str, Any]:
        material = await PipelineDao.get_owned_material(db, material_id, user_id)
        if not material:
            raise ServiceException(message='资料不存在或无权删除')
        local_path = cls._material_local_path(material.file_path)
        try:
            await PipelineDao.delete_material(db, material_id, user_id)
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        file_deleted = False
        if local_path and local_path.is_file():
            try:
                local_path.unlink()
                file_deleted = True
            except OSError:
                file_deleted = False
        return {'id': material_id, 'deleted': True, 'fileDeleted': file_deleted}

    @classmethod
    def _summarize_text(cls, text: str, limit: int = 220) -> str:
        compact = re.sub(r'\s+', ' ', text or '').strip()
        return compact if len(compact) <= limit else f'{compact[:limit].rstrip()}…'

    @classmethod
    async def list_workspace(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        rows = await PipelineDao.list_workspace_items(db, user_id)
        favorites = [item.item_id for item in rows if item.action == 'favorite']
        basket = [
            {
                'id': item.item_id,
                'title': item.title,
                'type': item.item_type,
                **dict(item.snapshot or {}),
            }
            for item in rows
            if item.action == 'basket'
        ]
        return {'favorites': favorites, 'basket': basket}

    @classmethod
    async def upsert_workspace_item(
        cls,
        db: AsyncSession,
        user_id: int,
        payload: PipelineWorkspaceItemMutationModel,
    ) -> dict[str, Any]:
        existing = await PipelineDao.get_workspace_item(
            db,
            user_id,
            payload.item_type,
            payload.item_id,
            payload.action,
        )
        if existing:
            existing.title = payload.title
            existing.item_type = payload.item_type
            existing.snapshot = payload.snapshot
        else:
            existing = PipelineWorkspaceItem(
                user_id=user_id,
                item_id=payload.item_id,
                item_type=payload.item_type,
                action=payload.action,
                title=payload.title,
                snapshot=payload.snapshot,
            )
            await PipelineDao.add_workspace_item(db, existing)
        await db.commit()
        return {'itemId': payload.item_id, 'action': payload.action, 'saved': True}

    @classmethod
    async def delete_workspace_item(
        cls,
        db: AsyncSession,
        user_id: int,
        item_id: str,
        action: str,
    ) -> dict[str, Any]:
        await PipelineDao.delete_workspace_item(db, user_id, item_id, action)
        await db.commit()
        return {'itemId': item_id, 'action': action, 'deleted': True}

    @classmethod
    def _queued_stage_rows(cls) -> list[dict[str, Any]]:
        return [{'key': key, 'label': label, 'status': 'waiting', 'progress': 0} for key, label in cls._stage_labels]

    @classmethod
    async def queue_research_job(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        payload: PipelineResearchJobCreateModel,
    ) -> dict[str, Any]:
        options = payload.options or {}
        if options.get('language') not in {None, 'zh'}:
            raise ServiceException(message='当前版本仅支持简体中文输出')
        if options.get('length') not in {None, 'standard'}:
            raise ServiceException(message='当前版本仅支持标准篇幅')
        if options.get('publicSupplement') is True:
            raise ServiceException(message='当前版本仅支持使用已选资料，公开资料补充尚未开放')
        if payload.template_id:
            template = await PipelineTemplateService.get_published(db, payload.template_id)
            if not template:
                raise ServiceException(message='所选模板不存在或尚未发布，请返回重新选择')
            if template.report_type != payload.report_type:
                raise ServiceException(message='模板与报告类型不匹配，请返回重新选择')
            if not payload.template_version:
                payload = payload.model_copy(update={'template_version': template.version_label})
            if not payload.outline:
                payload = payload.model_copy(update={'outline': list(template.sections or [])})
        now = datetime.now()
        job = PipelineResearchJob(
            task_id=f'job-{uuid4().hex[:16]}',
            user_id=user_id,
            owner_name=owner_name,
            title=payload.title,
            report_type=payload.report_type,
            template_id=payload.template_id,
            template_version=payload.template_version,
            status='queued',
            current_stage='validating',
            progress=0,
            config=payload.model_dump(by_alias=False),
            selected_items=[],
            outline=payload.outline or [],
            stages=cls._queued_stage_rows(),
            logs=[{'time': now.strftime('%H:%M:%S'), 'type': 'info', 'message': '任务已进入后台生成队列。'}],
            create_time=now,
            update_time=now,
        )
        await PipelineDao.add_research_job(db, job)
        await db.commit()
        await db.refresh(job)
        return cls._job_dict(job)

    @classmethod
    async def queue_research_job_retry(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        job_id: str,
    ) -> dict[str, Any]:
        job = await PipelineDao.get_research_job(db, job_id, user_id)
        if not job:
            raise ServiceException(message='科研生成任务不存在或无权访问')
        if job.status in {'queued', 'running'}:
            raise ServiceException(message='任务正在执行，请勿重复提交')
        now = datetime.now()
        job.status = 'queued'
        job.current_stage = 'validating'
        job.progress = 0
        job.stages = cls._queued_stage_rows()
        job.logs = [
            *(job.logs or []),
            {'time': now.strftime('%H:%M:%S'), 'type': 'info', 'message': '已按原配置重新加入后台生成队列。'},
        ]
        job.error_message = None
        job.update_time = now
        await db.commit()
        await db.refresh(job)
        return cls._job_dict(job)

    @classmethod
    async def _advance_research_job(
        cls,
        db: AsyncSession,
        job: PipelineResearchJob,
        stage_index: int,
        message: str,
    ) -> bool:
        await db.refresh(job)
        if job.status == 'cancelled':
            return False
        now = datetime.now()
        job.status = 'running'
        job.current_stage = cls._stage_labels[stage_index][0]
        job.progress = round(stage_index / len(cls._stage_labels) * 100)
        job.stages = [
            {
                'key': key,
                'label': label,
                'status': 'completed' if index < stage_index else 'running' if index == stage_index else 'waiting',
                'progress': round(index / len(cls._stage_labels) * 100),
            }
            for index, (key, label) in enumerate(cls._stage_labels)
        ]
        job.logs = [*(job.logs or []), {'time': now.strftime('%H:%M:%S'), 'type': 'info', 'message': message}]
        job.update_time = now
        await db.commit()
        return True

    @classmethod
    async def process_queued_research_job(  # noqa: PLR0912, PLR0915
        cls,
        *,
        job_id: str,
        user_id: int,
        owner_name: str,
    ) -> None:
        async with AsyncSessionLocal() as db:
            try:
                job = await PipelineDao.get_research_job(db, job_id, user_id)
                if not job or job.status == 'cancelled':
                    return
                config = dict(job.config or {})
                config.pop('generation_mode', None)
                payload = PipelineResearchJobCreateModel.model_validate(config)

                if not await cls._advance_research_job(db, job, 0, '正在校验资料权限和任务参数。'):
                    return
                evidence = await cls._resolve_evidence(db, user_id, payload.selected_item_ids, payload=payload)
                if payload.selected_item_ids and not evidence:
                    raise ServiceException(message='所选资料不存在、尚未解析或当前账号无权访问')
                job.selected_items = evidence
                await db.commit()

                if not await cls._advance_research_job(db, job, 1, f'已确认 {len(evidence)} 条可用资料的解析状态。'):
                    return
                if not await cls._advance_research_job(db, job, 2, '正在从所选资料中组织可追溯证据。'):
                    return
                outline = payload.outline or list(job.outline or []) or cls._default_outline(payload.report_type)
                job.outline = outline
                await db.commit()

                if not await cls._advance_research_job(db, job, 3, f'已形成 {len(outline)} 个章节的大纲与字数目标。'):
                    return
                sections, citations = cls._build_sections(payload, outline, evidence)
                if not await cls._advance_research_job(db, job, 4, f'已生成 {len(sections)} 个可编辑章节。'):
                    return
                if not await cls._advance_research_job(db, job, 5, f'已建立 {len(citations)} 条来源引用关系。'):
                    return
                quality_issues = cls._build_quality_issues(sections, citations, payload.citation_check)
                if not await cls._advance_research_job(
                    db, job, 6, f'质量检查完成，发现 {len(quality_issues)} 项待确认问题。'
                ):
                    return
                if not await cls._advance_research_job(db, job, 7, '已准备报告图形与结构化编辑数据。'):
                    return

                markdown = cls._build_markdown(payload.title, sections, citations)
                now = datetime.now()
                report = await PipelineDao.get_report_by_task(db, job.task_id, user_id)
                version_source = 'retry' if report else 'generated'
                if report:
                    report.title = payload.title
                    report.status = 'completed'
                    report.content = markdown
                    report.sections = sections
                    report.citations = citations
                    report.quality_issues = quality_issues
                    report.word_count = len(re.sub(r'\s+', '', markdown))
                    report.version_no += 1
                    report.update_time = now
                else:
                    report = PipelineReport(
                        report_id=f'report-{uuid4().hex[:16]}',
                        source_task_id=job.task_id,
                        user_id=user_id,
                        owner_name=owner_name,
                        title=payload.title,
                        report_type=payload.report_type,
                        status='completed',
                        version_no=1,
                        content=markdown,
                        sections=sections,
                        citations=citations,
                        quality_issues=quality_issues,
                        metadata_json={
                            'templateId': payload.template_id,
                            'templateVersion': payload.template_version,
                            'generationMode': 'template-evidence-background',
                            'period': payload.period,
                            **payload.options,
                        },
                        word_count=len(re.sub(r'\s+', '', markdown)),
                        create_time=now,
                        update_time=now,
                    )
                    await PipelineDao.add_report(db, report)

                await PipelineDao.add_report_version(
                    db,
                    PipelineReportVersion(
                        report_id=report.report_id,
                        version_no=report.version_no,
                        title=report.title,
                        content=report.content,
                        sections=report.sections,
                        citations=report.citations,
                        source=version_source,
                        operator_id=user_id,
                        operator_name=owner_name,
                        create_time=now,
                    ),
                )
                job.status = 'completed'
                job.current_stage = 'completed'
                job.progress = 100
                job.stages = [
                    {
                        'key': key,
                        'label': label,
                        'status': 'completed',
                        'progress': round((index + 1) / len(cls._stage_labels) * 100),
                    }
                    for index, (key, label) in enumerate(cls._stage_labels)
                ]
                job.logs = [
                    *(job.logs or []),
                    {'time': now.strftime('%H:%M:%S'), 'type': 'success', 'message': '报告与初始版本已生成完成。'},
                ]
                job.error_message = None
                job.update_time = now
                await db.commit()
            except Exception as exc:
                await db.rollback()
                job = await PipelineDao.get_research_job(db, job_id, user_id)
                if not job or job.status == 'cancelled':
                    return
                now = datetime.now()
                job.status = 'failed'
                job.current_stage = 'failed'
                job.error_message = getattr(exc, 'message', None) or str(exc) or '后台生成失败'
                job.logs = [
                    *(job.logs or []),
                    {'time': now.strftime('%H:%M:%S'), 'type': 'error', 'message': job.error_message},
                ]
                job.update_time = now
                await db.commit()

    @classmethod
    async def create_research_job(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        payload: PipelineResearchJobCreateModel,
    ) -> dict[str, Any]:
        evidence = await cls._resolve_evidence(db, user_id, payload.selected_item_ids)
        outline = payload.outline or cls._default_outline(payload.report_type)
        sections, citations = cls._build_sections(payload, outline, evidence)
        quality_issues = cls._build_quality_issues(sections, citations, payload.citation_check)
        markdown = cls._build_markdown(payload.title, sections, citations)
        now = datetime.now()
        job_id = f'job-{uuid4().hex[:16]}'
        report_id = f'report-{uuid4().hex[:16]}'
        stage_rows = [
            {
                'key': key,
                'label': label,
                'status': 'completed',
                'progress': round((index + 1) / len(cls._stage_labels) * 100),
            }
            for index, (key, label) in enumerate(cls._stage_labels)
        ]
        logs = [
            {'time': now.strftime('%H:%M:%S'), 'type': 'success', 'message': f'已校验 {len(evidence)} 条可用证据。'},
            {'time': now.strftime('%H:%M:%S'), 'type': 'success', 'message': f'已生成 {len(sections)} 个结构化章节。'},
            {
                'time': now.strftime('%H:%M:%S'),
                'type': 'info' if quality_issues else 'success',
                'message': f'质量检查完成，发现 {len(quality_issues)} 项待确认问题。',
            },
        ]
        config = payload.model_dump(by_alias=False)
        config['generation_mode'] = 'template-evidence'
        job = PipelineResearchJob(
            task_id=job_id,
            user_id=user_id,
            owner_name=owner_name,
            title=payload.title,
            report_type=payload.report_type,
            template_id=payload.template_id,
            template_version=payload.template_version,
            status='completed',
            current_stage='completed',
            progress=100,
            config=config,
            selected_items=evidence,
            outline=outline,
            stages=stage_rows,
            logs=logs,
            create_time=now,
            update_time=now,
        )
        report = PipelineReport(
            report_id=report_id,
            source_task_id=job_id,
            user_id=user_id,
            owner_name=owner_name,
            title=payload.title,
            report_type=payload.report_type,
            status='completed',
            version_no=1,
            content=markdown,
            sections=sections,
            citations=citations,
            quality_issues=quality_issues,
            metadata_json={
                'templateId': payload.template_id,
                'templateVersion': payload.template_version,
                'generationMode': 'template-evidence',
                'period': payload.period,
                **payload.options,
            },
            word_count=len(re.sub(r'\s+', '', markdown)),
            create_time=now,
            update_time=now,
        )
        version = PipelineReportVersion(
            report_id=report_id,
            version_no=1,
            title=payload.title,
            content=markdown,
            sections=sections,
            citations=citations,
            source='generated',
            operator_id=user_id,
            operator_name=owner_name,
            create_time=now,
        )
        try:
            await PipelineDao.add_research_job(db, job)
            await PipelineDao.add_report(db, report)
            await PipelineDao.add_report_version(db, version)
            await db.commit()
            return cls._job_dict(job, report_id)
        except Exception:
            await db.rollback()
            raise

    @classmethod
    async def _resolve_evidence(
        cls,
        db: AsyncSession,
        user_id: int,
        selected_ids: list[str],
        payload: PipelineResearchJobCreateModel | None = None,
    ) -> list[dict[str, Any]]:
        if not selected_ids:
            return []
        materials = await PipelineDao.list_accessible_materials(db, user_id)
        persistent = {
            item.file_id: {
                'id': item.file_id,
                'type': item.category,
                'title': item.name,
                'summary': item.summary or cls._summarize_text(item.extracted_text or ''),
                'source': item.owner_name,
                'location': '基础文本提取' if item.extracted_text else '资料摘要',
            }
            for item in materials
            if item.parse_status == 'indexed'
            and getattr(item, 'allow_ai_use', True)
            and (item.extracted_text or item.summary)
        }
        unresolved_ids = set(selected_ids) - persistent.keys()
        intelligence_items: dict[str, dict[str, Any]] = {}
        report_type = payload.report_type if payload else ''
        period = list(payload.period or []) if payload else []

        def in_digest_period(value: datetime | None) -> bool:
            if report_type not in {'daily', 'weekly', 'monthly'} or not period:
                return True
            if value is None or len(period) not in {1, 2}:
                return False
            try:
                start = datetime.fromisoformat(period[0]).replace(hour=0, minute=0, second=0, microsecond=0)
                end = datetime.fromisoformat(period[-1]).replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                return False
            if len(period) == 1:
                end = start
            return start <= value.replace(tzinfo=None) < end + timedelta(days=1)

        for item in await PipelineDao.list_articles(db):
            if (
                item.article_id not in unresolved_ids
                or getattr(item, 'review_status', 'approved') != 'approved'
                or not in_digest_period(item.published_time)
            ):
                continue
            intelligence_items[item.article_id] = {
                'id': item.article_id,
                'type': '科技资讯',
                'title': item.title,
                'summary': item.summary or cls._summarize_text(item.body or ''),
                'source': item.source_name or '未知来源',
                'location': cls._datetime_text(item.published_time),
            }
        for item in await PipelineDao.list_papers(db):
            # 论文当前只保存发表年份，不能伪装成某个日报或周报的精确来源。
            if (
                item.paper_id not in unresolved_ids
                or getattr(item, 'review_status', 'approved') != 'approved'
                or report_type in {'daily', 'weekly', 'monthly'}
            ):
                continue
            intelligence_items[item.paper_id] = {
                'id': item.paper_id,
                'type': '论文',
                'title': item.title,
                'summary': item.abstract_text or '',
                'source': item.source_name or item.journal or '论文数据库',
                'location': str(item.publication_year or ''),
            }
        all_items = {**intelligence_items, **persistent}
        result = [all_items[item_id] for item_id in selected_ids if item_id in all_items]
        if payload and report_type in {'daily', 'weekly', 'monthly'} and payload.options.get('duplicateMerge'):
            seen_titles: set[str] = set()
            deduplicated = []
            for item in result:
                normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', item.get('title', '')).lower()[:32]
                if normalized and normalized in seen_titles:
                    continue
                seen_titles.add(normalized)
                deduplicated.append(item)
            result = deduplicated
        if payload and report_type in {'daily', 'weekly', 'monthly'}:
            try:
                per_direction = max(1, int(payload.options.get('itemCount') or len(result) or 1))
            except (TypeError, ValueError):
                per_direction = max(1, len(result) or 1)
            directions = payload.options.get('directions') or [payload.direction]
            direction_count = max(1, len(directions) if isinstance(directions, list) else 1)
            result = result[: per_direction * direction_count]
        return result

    @classmethod
    def _default_outline(cls, report_type: str) -> list[dict[str, Any]]:
        if report_type == 'monthly':
            return [
                {'id': 1, 'title': '月度要闻', 'words': 1600},
                {'id': 2, 'title': '重点技术进展', 'words': 1800},
                {'id': 3, 'title': '行业趋势与变化', 'words': 1500},
                {'id': 4, 'title': '管网应用与实践', 'words': 1500},
                {'id': 5, 'title': '风险与机会研判', 'words': 1200},
                {'id': 6, 'title': '下月关注', 'words': 800},
            ]
        if report_type in {'daily', 'weekly'}:
            return [
                {'id': 1, 'title': '本期要闻', 'words': 1200},
                {'id': 2, 'title': '检测技术进展', 'words': 1200},
                {'id': 3, 'title': '应力监测动态', 'words': 1000},
                {'id': 4, 'title': '完整性管理实践', 'words': 1000},
                {'id': 5, 'title': '趋势研判', 'words': 800},
            ]
        return [
            {'id': 1, 'title': '项目背景与问题分析', 'words': 1800},
            {'id': 2, 'title': '国内外技术现状', 'words': 2200},
            {'id': 3, 'title': '研究目标与主要内容', 'words': 2000},
            {'id': 4, 'title': '技术路线与试验方案', 'words': 2800},
            {'id': 5, 'title': '考核指标与预期成果', 'words': 1200},
            {'id': 6, 'title': '进度计划与经费需求', 'words': 1000},
        ]

    @classmethod
    def _build_sections(
        cls,
        payload: PipelineResearchJobCreateModel,
        outline: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        citations = [
            {
                'id': index,
                'sourceId': item['id'],
                'type': item.get('type', '资料'),
                'title': item.get('title', '未命名资料'),
                'location': item.get('location', '资料摘要'),
                'quote': item.get('summary', '等待补充证据摘要'),
                'source': item.get('source', '平台知识库'),
            }
            for index, item in enumerate(evidence, start=1)
        ]
        sections = []
        for index, raw_section in enumerate(outline, start=1):
            title = str(raw_section.get('title') or raw_section.get('heading') or f'第{index}章').strip()
            linked = (
                citations[(index - 1) % len(citations) :] + citations[: (index - 1) % len(citations)]
                if citations
                else []
            )
            linked = linked[: min(3, len(linked))]
            content = cls._build_section_content(payload, title, linked)
            sections.append(
                {
                    'id': raw_section.get('id', index),
                    'title': title,
                    'targetWords': int(raw_section.get('words') or 1000),
                    'words': len(re.sub(r'\s+', '', content)),
                    'sources': len(linked),
                    'citations': len(linked),
                    'citationIds': [item['id'] for item in linked],
                    'status': 'complete' if linked else 'warning',
                    'content': content,
                }
            )
        return sections, citations

    @classmethod
    def _build_section_content(
        cls,
        payload: PipelineResearchJobCreateModel,
        section_title: str,
        citations: list[dict[str, Any]],
    ) -> str:
        direction = payload.direction or '管网科技创新'
        scenario = payload.scenario or '工程应用'
        requirements = payload.requirements.strip() or '兼顾技术可行性、现场验证与成果转化。'
        quote_length = {'short': 90, 'normal': 160, 'long': 260}.get(
            str(payload.options.get('summaryLength') or 'normal'),
            160,
        )
        evidence_text = '；'.join(
            f'{item["title"]}指出“{cls._summarize_text(item["quote"], quote_length)}”[{item["id"]}]' for item in citations
        )
        if payload.report_type in {'daily', 'weekly', 'monthly'}:
            return (
                f'本栏目围绕{direction}汇总本周期可信信息。{evidence_text or "当前没有匹配证据，需补充来源后再发布。"}'
                f'综合研判应关注技术成熟度、数据质量和现场适用边界，避免将单一来源结论直接用于工程决策。'
            )
        return (
            f'本节围绕“{section_title}”分析{direction}在{scenario}中的需求与实施边界。{requirements}'
            f'{evidence_text or "当前章节缺少直接证据，需要补充授权资料。"}'
            '建议采用可追溯证据链组织论证，明确数据来源、适用条件、人工复核节点和可量化验收指标。'
        )

    @classmethod
    def _build_quality_issues(
        cls,
        sections: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        citation_check: bool,
    ) -> list[dict[str, Any]]:
        issues = []
        if citation_check and not citations:
            issues.append({'level': 'high', 'title': '报告缺少可验证来源', 'description': '请至少选择一条已授权资料。'})
        issues.extend(
            {
                'level': 'medium',
                'sectionId': section['id'],
                'title': f'“{section["title"]}”证据覆盖不足',
                'description': '当前章节关联来源少于 2 条，建议补充交叉验证资料。',
            }
            for section in sections
            if section['sources'] < cls._minimum_section_sources
        )
        return issues

    @classmethod
    def _build_markdown(
        cls,
        title: str,
        sections: list[dict[str, Any]],
        citations: list[dict[str, Any]],
    ) -> str:
        lines = [f'# {title}', '', f'> 生成时间：{cls._now_text()}；生成模式：模板与证据编排。', '']
        for index, section in enumerate(sections, start=1):
            lines.extend([f'## {index}. {section["title"]}', '', section['content'], ''])
        lines.extend(['## 参考资料', ''])
        if citations:
            lines.extend(
                f'[{item["id"]}] {item["title"]}（{item["source"]}，{item["location"]}）' for item in citations
            )
        else:
            lines.append('- 当前版本尚未关联可验证资料。')
        return '\n'.join(lines).strip() + '\n'

    @classmethod
    def _job_dict(cls, job: PipelineResearchJob, report_id: str | None = None) -> dict[str, Any]:
        status_labels = {
            'queued': '等待生成',
            'running': '生成中',
            'completed': '已完成',
            'failed': '生成失败',
            'cancelled': '已取消',
        }
        return {
            'id': job.task_id,
            'jobId': job.task_id,
            'title': job.title,
            'type': job.report_type,
            'status': job.status,
            'statusLabel': status_labels.get(job.status, job.status),
            'stage': job.current_stage,
            'progress': job.progress,
            'owner': job.owner_name,
            'reportId': report_id,
            'selectedItems': list(job.selected_items or []),
            'outline': list(job.outline or []),
            'stages': list(job.stages or []),
            'logs': list(job.logs or []),
            'config': dict(job.config or {}),
            'errorMessage': job.error_message or '',
            'createdAt': cls._datetime_text(job.create_time),
            'updatedAt': cls._datetime_text(job.update_time),
        }

    @classmethod
    def _report_dict(cls, report: PipelineReport) -> dict[str, Any]:
        metadata = dict(report.metadata_json or {})
        return {
            'id': report.report_id,
            'reportId': report.report_id,
            'jobId': report.source_task_id,
            'title': report.title,
            'type': report.report_type,
            'reportType': report.report_type,
            'status': report.status,
            'owner': report.owner_name,
            'version': f'V{report.version_no}.0',
            'versionNo': report.version_no,
            'content': report.content,
            'sections': list(report.sections or []),
            'citations': list(report.citations or []),
            'qualityIssues': list(report.quality_issues or []),
            'metadata': metadata,
            'words': report.word_count,
            'sources': len(report.citations or []),
            'coverage': len(report.citations or []),
            'period': ' 至 '.join(metadata.get('period') or []),
            'updatedAt': cls._datetime_text(report.update_time),
            'updated_at': cls._datetime_text(report.update_time),
            'revision': report.update_time.isoformat(timespec='microseconds') if report.update_time else '',
            'createdAt': cls._datetime_text(report.create_time),
        }

    @classmethod
    async def list_research_jobs(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        rows = await PipelineDao.list_research_jobs(db, user_id)
        reports = await PipelineDao.list_reports_by_tasks(db, [item.task_id for item in rows], user_id)
        report_ids = {item.source_task_id: item.report_id for item in reports}
        return {
            'rows': [cls._job_dict(item, report_ids.get(item.task_id)) for item in rows],
            'total': len(rows),
        }

    @classmethod
    async def get_research_job(cls, db: AsyncSession, user_id: int, job_id: str) -> dict[str, Any]:
        job = await PipelineDao.get_research_job(db, job_id, user_id)
        if not job:
            raise ServiceException(message='科研生成任务不存在或无权访问')
        report = await PipelineDao.get_report_by_task(db, job.task_id, user_id)
        return cls._job_dict(job, report.report_id if report else None)

    @classmethod
    async def cancel_research_job(cls, db: AsyncSession, user_id: int, job_id: str) -> dict[str, Any]:
        job = await PipelineDao.get_research_job(db, job_id, user_id)
        if not job:
            raise ServiceException(message='科研生成任务不存在或无权访问')
        if job.status == 'completed':
            raise ServiceException(message='任务已经完成，不能取消；如需调整请打开报告编辑或重新生成')
        if job.status == 'cancelled':
            return cls._job_dict(job)

        now = datetime.now()
        stages = [dict(item) for item in (job.stages or [])]
        for stage in stages:
            if stage.get('status') == 'running':
                stage['status'] = 'cancelled'
        job.status = 'cancelled'
        job.current_stage = 'cancelled'
        job.stages = stages
        job.logs = [
            *(job.logs or []),
            {'time': now.strftime('%H:%M:%S'), 'type': 'warning', 'message': '任务已由用户取消。'},
        ]
        job.update_time = now
        await db.commit()
        await db.refresh(job)
        return cls._job_dict(job)

    @classmethod
    async def retry_research_job(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        owner_name: str,
        job_id: str,
    ) -> dict[str, Any]:
        job = await PipelineDao.get_research_job(db, job_id, user_id)
        if not job:
            raise ServiceException(message='科研生成任务不存在或无权访问')

        config = dict(job.config or {})
        config.pop('generation_mode', None)
        payload = PipelineResearchJobCreateModel.model_validate(config)
        evidence = await cls._resolve_evidence(db, user_id, payload.selected_item_ids)
        outline = payload.outline or list(job.outline or []) or cls._default_outline(payload.report_type)
        sections, citations = cls._build_sections(payload, outline, evidence)
        quality_issues = cls._build_quality_issues(sections, citations, payload.citation_check)
        markdown = cls._build_markdown(payload.title, sections, citations)
        now = datetime.now()

        job.status = 'completed'
        job.current_stage = 'completed'
        job.progress = 100
        job.selected_items = evidence
        job.outline = outline
        job.stages = [
            {
                'key': key,
                'label': label,
                'status': 'completed',
                'progress': round((index + 1) / len(cls._stage_labels) * 100),
            }
            for index, (key, label) in enumerate(cls._stage_labels)
        ]
        job.logs = [
            *(job.logs or []),
            {'time': now.strftime('%H:%M:%S'), 'type': 'info', 'message': '已按原任务配置重新执行生成。'},
            {
                'time': now.strftime('%H:%M:%S'),
                'type': 'success',
                'message': f'重新生成完成，共形成 {len(sections)} 个章节和 {len(citations)} 条引用。',
            },
        ]
        job.error_message = None
        job.update_time = now

        report = await PipelineDao.get_report_by_task(db, job.task_id, user_id)
        if report:
            report.title = payload.title
            report.status = 'completed'
            report.content = markdown
            report.sections = sections
            report.citations = citations
            report.quality_issues = quality_issues
            report.word_count = len(re.sub(r'\s+', '', markdown))
            report.version_no += 1
            report.update_time = now
        else:
            report_id = f'report-{uuid4().hex[:16]}'
            report = PipelineReport(
                report_id=report_id,
                source_task_id=job.task_id,
                user_id=user_id,
                owner_name=owner_name,
                title=payload.title,
                report_type=payload.report_type,
                status='completed',
                version_no=1,
                content=markdown,
                sections=sections,
                citations=citations,
                quality_issues=quality_issues,
                metadata_json={
                    'templateId': payload.template_id,
                    'templateVersion': payload.template_version,
                    'generationMode': 'template-evidence',
                    'period': payload.period,
                    **payload.options,
                },
                word_count=len(re.sub(r'\s+', '', markdown)),
                create_time=now,
                update_time=now,
            )
            await PipelineDao.add_report(db, report)

        await PipelineDao.add_report_version(
            db,
            PipelineReportVersion(
                report_id=report.report_id,
                version_no=report.version_no,
                title=report.title,
                content=report.content,
                sections=report.sections,
                citations=report.citations,
                source='retry',
                operator_id=user_id,
                operator_name=owner_name,
                create_time=now,
            ),
        )
        await db.commit()
        await db.refresh(job)
        return cls._job_dict(job, report.report_id)

    @classmethod
    async def list_reports(cls, db: AsyncSession, user_id: int) -> dict[str, Any]:
        rows = await PipelineDao.list_reports(db, user_id)
        return {'rows': [cls._report_dict(item) for item in rows], 'total': len(rows)}

    @classmethod
    async def get_report(cls, db: AsyncSession, user_id: int, report_id: str) -> dict[str, Any]:
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        return cls._report_dict(report)

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
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        if payload.expected_version is not None and report.version_no != payload.expected_version:
            raise ServiceException(message='报告版本已变化，请刷新后再保存')
        expected_revision = None
        if payload.expected_revision:
            try:
                expected_revision = datetime.fromisoformat(payload.expected_revision)
            except ValueError as exc:
                raise ServiceException(message='报告修订标记无效，请刷新后再保存') from exc
            if report.update_time != expected_revision:
                raise ServiceException(message='报告已被其他页面修改，请刷新后再保存')

        if expected_revision:
            now = datetime.now()
            next_version = report.version_no + 1 if payload.save_version else report.version_no
            values = {
                'title': payload.title if payload.title is not None else report.title,
                'content': payload.content if payload.content is not None else report.content,
                'sections': payload.sections if payload.sections is not None else report.sections,
                'citations': payload.citations if payload.citations is not None else report.citations,
                'quality_issues': payload.quality_issues
                if payload.quality_issues is not None
                else report.quality_issues,
                'status': payload.status if payload.status is not None else report.status,
                'word_count': len(
                    re.sub(
                        r'\s+',
                        '',
                        payload.content if payload.content is not None else report.content,
                    )
                ),
                'update_time': now,
            }
            if payload.save_version:
                values['version_no'] = next_version
            result = await db.execute(
                update(PipelineReport)
                .where(
                    PipelineReport.report_id == report_id,
                    PipelineReport.user_id == user_id,
                    PipelineReport.update_time == expected_revision,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                await db.rollback()
                raise ServiceException(message='报告已被其他页面修改，请刷新后再保存')
            if payload.save_version:
                await PipelineDao.add_report_version(
                    db,
                    PipelineReportVersion(
                        report_id=report.report_id,
                        version_no=next_version,
                        title=values['title'],
                        content=values['content'],
                        sections=values['sections'],
                        citations=values['citations'],
                        source=payload.version_source,
                        operator_id=user_id,
                        operator_name=owner_name,
                    ),
                )
            await db.commit()
            await db.refresh(report)
            return cls._report_dict(report)
        if payload.title is not None:
            report.title = payload.title
        if payload.content is not None:
            report.content = payload.content
            report.word_count = len(re.sub(r'\s+', '', payload.content))
        if payload.sections is not None:
            report.sections = payload.sections
        if payload.citations is not None:
            report.citations = payload.citations
        if payload.quality_issues is not None:
            report.quality_issues = payload.quality_issues
        if payload.status is not None:
            report.status = payload.status
        report.update_time = datetime.now()
        if payload.save_version:
            report.version_no += 1
            await PipelineDao.add_report_version(
                db,
                PipelineReportVersion(
                    report_id=report.report_id,
                    version_no=report.version_no,
                    title=report.title,
                    content=report.content,
                    sections=report.sections,
                    citations=report.citations,
                    source=payload.version_source,
                    operator_id=user_id,
                    operator_name=owner_name,
                ),
            )
        await db.commit()
        await db.refresh(report)
        return cls._report_dict(report)

    @classmethod
    async def get_report_diagram(cls, db: AsyncSession, user_id: int, report_id: str) -> dict[str, Any]:
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        stored = dict(report.metadata_json or {}).get('diagram') or {}
        return {
            'reportId': report.report_id,
            'schemaVersion': int(stored.get('schemaVersion') or 1),
            'savedAt': str(stored.get('savedAt') or ''),
            'diagram': stored.get('data'),
        }

    @classmethod
    async def update_report_diagram(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        report_id: str,
        payload: PipelineDiagramUpdateModel,
    ) -> dict[str, Any]:
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        stages = payload.diagram.get('stages')
        if not isinstance(stages, dict):
            raise ServiceException(message='图形数据缺少有效的阶段结构')

        now = datetime.now()
        saved_at = now.isoformat(timespec='seconds')
        metadata = dict(report.metadata_json or {})
        metadata['diagram'] = {
            'schemaVersion': payload.schema_version,
            'savedAt': saved_at,
            'data': payload.diagram,
        }
        report.metadata_json = metadata
        report.update_time = now
        await db.commit()
        await db.refresh(report)
        return {
            'reportId': report.report_id,
            'schemaVersion': payload.schema_version,
            'savedAt': saved_at,
            'diagram': payload.diagram,
        }

    @classmethod
    async def list_report_versions(cls, db: AsyncSession, user_id: int, report_id: str) -> dict[str, Any]:
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        rows = await PipelineDao.list_report_versions(db, report_id)
        return {
            'rows': [
                {
                    'version': f'V{item.version_no}.0',
                    'versionNo': item.version_no,
                    'title': item.title,
                    'source': item.source,
                    'operator': item.operator_name,
                    'createdAt': cls._datetime_text(item.create_time),
                }
                for item in rows
            ],
            'total': len(rows),
        }

    @classmethod
    async def get_report_version(
        cls,
        db: AsyncSession,
        user_id: int,
        report_id: str,
        version_no: int,
    ) -> dict[str, Any]:
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        version = await PipelineDao.get_report_version(db, report_id, version_no)
        if not version:
            raise ServiceException(message='报告版本不存在')
        return {
            'reportId': report_id,
            'version': f'V{version.version_no}.0',
            'versionNo': version.version_no,
            'title': version.title,
            'content': version.content,
            'sections': list(version.sections or []),
            'citations': list(version.citations or []),
            'source': version.source,
            'operator': version.operator_name,
            'createdAt': cls._datetime_text(version.create_time),
        }

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
        report = await PipelineDao.get_report(db, report_id, user_id)
        if not report:
            raise ServiceException(message='报告不存在或无权访问')
        version = await PipelineDao.get_report_version(db, report_id, version_no)
        if not version:
            raise ServiceException(message='报告版本不存在')

        report.title = version.title
        report.content = version.content
        report.sections = list(version.sections or [])
        report.citations = list(version.citations or [])
        report.word_count = len(re.sub(r'\s+', '', report.content or ''))
        report.version_no += 1
        report.update_time = datetime.now()
        await PipelineDao.add_report_version(
            db,
            PipelineReportVersion(
                report_id=report.report_id,
                version_no=report.version_no,
                title=report.title,
                content=report.content,
                sections=report.sections,
                citations=report.citations,
                source='restored',
                operator_id=user_id,
                operator_name=owner_name,
            ),
        )
        await db.commit()
        await db.refresh(report)
        return cls._report_dict(report)
