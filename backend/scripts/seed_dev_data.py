"""Seed a small, repeatable PipeSight dataset for local development only."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import select

# Allow ``python scripts/seed_dev_data.py`` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.database import AsyncSessionLocal
from config.env import AppConfig
# Register the small set of referenced RuoYi tables before SQLAlchemy flushes
# the pipeline models (the app normally imports these through auto-registration).
from module_admin.entity.do import job_do, menu_do, role_do, user_do  # noqa: F401
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


async def seed() -> None:
    if AppConfig.app_env != 'dev':
        raise SystemExit('开发种子数据只允许在 APP_ENV=dev 下执行')

    now = datetime.now().replace(microsecond=0)
    async with AsyncSessionLocal() as db:
        sources = {
            'source-news': PipelineSource(
                source_id='source-news',
                source_code='pipe-news',
                name='国家管网科技资讯',
                source_type='news',
                endpoint='https://www.pipechina.com.cn',
                adapter_key='rss',
                schedule_cron='0 */2 * * *',
                status='active',
                enabled=True,
                config_json={'categories': ['管网安全', '检测技术']},
                handoff_mode='local',
                last_run_time=now - timedelta(minutes=18),
                last_run_status='success',
                success_count=26,
                failure_count=1,
                consecutive_failures=0,
                owner_id=1,
                create_time=now - timedelta(days=12),
                update_time=now - timedelta(minutes=18),
            ),
            'source-paper': PipelineSource(
                source_id='source-paper',
                source_code='pipe-papers',
                name='管网论文资料库',
                source_type='paper',
                endpoint='https://scholar.google.com',
                adapter_key='crossref',
                schedule_cron='0 3 * * 1',
                status='active',
                enabled=True,
                config_json={'keywords': ['pipeline integrity', 'stress monitoring']},
                handoff_mode='local',
                last_run_time=now - timedelta(hours=3),
                last_run_status='success',
                success_count=12,
                failure_count=0,
                consecutive_failures=0,
                owner_id=1,
                create_time=now - timedelta(days=12),
                update_time=now - timedelta(hours=3),
            ),
        }
        for source_id, source in sources.items():
            if await db.scalar(select(PipelineSource).where(PipelineSource.source_id == source_id)) is None:
                db.add(source)
        await db.flush()

        if await db.scalar(select(PipelineCrawlRun).where(PipelineCrawlRun.run_id == 'run-demo-news')) is None:
            db.add(
                PipelineCrawlRun(
                    run_id='run-demo-news',
                    source_id='source-news',
                    trigger_type='schedule',
                    status='success',
                    config_snapshot={'demo': True},
                    started_at=now - timedelta(minutes=22),
                    finished_at=now - timedelta(minutes=18),
                    fetched_count=18,
                    inserted_count=7,
                    updated_count=4,
                    duplicate_count=7,
                    handoff_status='completed',
                    handoff_count=0,
                    handoff_processed_count=0,
                    handoff_failed_count=0,
                    checkpoint_json={'page': 1},
                    create_time=now - timedelta(minutes=22),
                    update_time=now - timedelta(minutes=18),
                )
            )
        await db.flush()

        articles = [
            PipelineArticle(
                article_id='news-001',
                article_type='news',
                title='国家管网推进管道完整性管理数字化升级',
                canonical_url='https://www.pipechina.com.cn/demo/news-001',
                url_hash='demo-url-news-001',
                source_id='source-news',
                source_name='国家管网科技资讯',
                collection_run_id='run-demo-news',
                author_text='国家管网科技创新部',
                published_time=now - timedelta(hours=5),
                discovered_time=now - timedelta(hours=5),
                language='zh-CN',
                summary='围绕风险识别、状态评价和维修决策建立统一的数据闭环。',
                body='本文介绍管道完整性管理平台的建设重点，包括多源检测数据接入、风险分级和闭环处置。',
                article_hash='demo-article-news-001',
                relevance_score=96,
                review_status='approved',
                permission_scope='public',
                tags=['管网安全', '数字孪生'],
                metadata_json={'entities': ['管道完整性管理'], 'timeline': ['数据接入', '风险评价', '闭环处置']},
                analysis_version='demo-v1',
                handoff_status='completed',
                version_no=1,
                create_time=now - timedelta(hours=5),
                update_time=now - timedelta(hours=5),
            ),
            PipelineArticle(
                article_id='news-002',
                article_type='wechat',
                title='磁应力监测：从现场信号到可追溯研判',
                canonical_url='https://www.pipechina.com.cn/demo/news-002',
                url_hash='demo-url-news-002',
                source_id='source-news',
                source_name='国家管网科技资讯',
                collection_run_id='run-demo-news',
                author_text='管道技术前沿',
                published_time=now - timedelta(days=1),
                discovered_time=now - timedelta(days=1),
                language='zh-CN',
                summary='整理磁应力监测在异常识别、趋势分析和现场复核中的应用方法。',
                body='通过统一指标、测点和时间轴，监测结果可以直接进入科研报告和日报周月报。',
                article_hash='demo-article-news-002',
                relevance_score=91,
                review_status='approved',
                permission_scope='public',
                tags=['应力监测', '检测技术'],
                metadata_json={'entities': ['磁应力监测'], 'timeline': ['采集', '分析', '复核']},
                analysis_version='demo-v1',
                handoff_status='completed',
                version_no=1,
                create_time=now - timedelta(days=1),
                update_time=now - timedelta(days=1),
            ),
            PipelineArticle(
                article_id='news-003',
                article_type='news',
                title='多元检测数据融合支撑智能巡检决策',
                canonical_url='https://www.pipechina.com.cn/demo/news-003',
                url_hash='demo-url-news-003',
                source_id='source-news',
                source_name='国家管网科技资讯',
                collection_run_id='run-demo-news',
                author_text='能源科技观察',
                published_time=now - timedelta(days=2),
                discovered_time=now - timedelta(days=2),
                language='zh-CN',
                summary='融合内检测、外检测和运行数据，形成面向巡检任务的风险画像。',
                body='示例内容用于演示情报详情、关联主题和科研引用流程。',
                article_hash='demo-article-news-003',
                relevance_score=88,
                review_status='approved',
                permission_scope='public',
                tags=['智能巡检', '多元检测数据融合'],
                metadata_json={'entities': ['智能巡检'], 'timeline': ['数据融合', '风险画像', '任务编排']},
                analysis_version='demo-v1',
                handoff_status='completed',
                version_no=1,
                create_time=now - timedelta(days=2),
                update_time=now - timedelta(days=2),
            ),
        ]
        for article in articles:
            if await db.scalar(select(PipelineArticle).where(PipelineArticle.article_id == article.article_id)) is None:
                db.add(article)

        paper = PipelinePaper(
            paper_id='paper-001',
            title='Pipeline integrity assessment using multi-source monitoring data',
            canonical_url='https://doi.org/10.1016/j.engfailanal.2025.108123',
            source_id='source-paper',
            source_name='管网论文资料库',
            authors='Zhang Wei; Li Ming; Chen Yu',
            authors_json=['Zhang Wei', 'Li Ming', 'Chen Yu'],
            keywords=['pipeline integrity', 'stress monitoring', 'data fusion'],
            doi='10.1016/j.engfailanal.2025.108123',
            doi_normalized='10.1016/j.engfailanal.2025.108123',
            external_id='crossref-demo-001',
            journal='Engineering Failure Analysis',
            publisher='Elsevier',
            publication_year=2025,
            abstract_text=(
                'This study presents a traceable workflow for combining stress, corrosion and inspection data '
                'in pipeline integrity assessment.'
            ),
            full_text_url='https://doi.org/10.1016/j.engfailanal.2025.108123',
            citation_count=18,
            open_access_status='unknown',
            full_text_status='available',
            review_status='approved',
            permission_scope='public',
            tags=['检测技术', '管网安全'],
            metadata_json={
                'relevanceScore': 94,
                'entities': ['integrity assessment'],
                'timeline': ['monitoring', 'fusion', 'assessment'],
            },
            handoff_status='completed',
            create_time=now - timedelta(days=3),
            update_time=now - timedelta(days=3),
        )
        if await db.scalar(select(PipelinePaper).where(PipelinePaper.paper_id == paper.paper_id)) is None:
            db.add(paper)

        material = PipelineMaterial(
            file_id='file-demo-001',
            name='管道本体应力监测研究资料.docx',
            category='内部文献',
            file_name='file-demo-001.docx',
            file_path='dev-seed/file-demo-001.docx',
            file_url=None,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            file_size=18432,
            file_hash='demo-file-hash-001',
            permission_scope='private',
            allow_download=False,
            allow_ai_use=True,
            parse_status='indexed',
            parse_message='开发环境示例资料，已完成文本索引',
            summary='用于演示科研报告生成的示例资料，包含测点、异常区段和复核建议。',
            extracted_text='管道本体应力监测资料示例：重点关注高风险区段、监测趋势和现场复核。',
            tags=['应力监测', '科研报告'],
            metadata_json={'demo': True},
            version_no=1,
            owner_id=2,
            owner_name='年糕',
            create_time=now - timedelta(days=2),
            update_time=now - timedelta(days=2),
        )
        if await db.scalar(select(PipelineMaterial).where(PipelineMaterial.file_id == material.file_id)) is None:
            db.add(material)

        task = PipelineResearchJob(
            task_id='task-demo-001',
            user_id=2,
            owner_name='年糕',
            title='管道本体应力监测科研需求报告',
            report_type='research',
            template_id='template-01',
            template_version='V1.0',
            status='completed',
            current_stage='completed',
            progress=100,
            config={'topic': '管道本体应力监测', 'demo': True},
            selected_items=[{'id': 'file-demo-001', 'type': 'material', 'title': material.name}],
            outline=[{'title': '研究背景'}, {'title': '监测方案'}, {'title': '实施计划'}],
            stages=[{'key': 'completed', 'label': '任务完成', 'status': 'completed'}],
            logs=['已完成资料校验', '已生成报告初稿'],
            create_time=now - timedelta(hours=2),
            update_time=now - timedelta(minutes=12),
        )
        if await db.scalar(select(PipelineResearchJob).where(PipelineResearchJob.task_id == task.task_id)) is None:
            db.add(task)
        await db.flush()

        report = PipelineReport(
            report_id='report-demo-001',
            source_task_id='task-demo-001',
            user_id=2,
            owner_name='年糕',
            title='管道本体应力监测科研需求报告',
            report_type='research',
            status='draft',
            version_no=1,
            content=(
                '# 管道本体应力监测科研需求报告\n\n'
                '## 研究背景\n基于监测数据建立可追溯的风险识别流程。\n\n'
                '## 实施计划\n完成数据接入、指标校验和现场复核。'
            ),
            sections=[
                {'id': 'section-1', 'title': '研究背景', 'content': '基于监测数据建立可追溯的风险识别流程。'},
                {'id': 'section-2', 'title': '实施计划', 'content': '完成数据接入、指标校验和现场复核。'},
            ],
            citations=[{'id': 'file-demo-001', 'title': material.name, 'type': 'material'}],
            quality_issues=[],
            metadata_json={'demo': True},
            word_count=92,
            create_time=now - timedelta(hours=2),
            update_time=now - timedelta(minutes=10),
        )
        if await db.scalar(select(PipelineReport).where(PipelineReport.report_id == report.report_id)) is None:
            db.add(report)
            await db.flush()
            db.add(
                PipelineReportVersion(
                    report_id=report.report_id,
                    version_no=1,
                    title=report.title,
                    content=report.content,
                    sections=report.sections,
                    citations=report.citations,
                    quality_issues=[],
                    model_snapshot={'provider': 'template', 'version': 'demo-v1'},
                    source='generated',
                    operator_id=2,
                    operator_name='年糕',
                    create_time=report.create_time,
                )
            )

        if await db.scalar(
            select(PipelineWorkspaceItem).where(
                PipelineWorkspaceItem.user_id == 2,
                PipelineWorkspaceItem.item_id == 'news-001',
                PipelineWorkspaceItem.item_type == 'article',
                PipelineWorkspaceItem.action == 'favorite',
            )
        ) is None:
            db.add(
                PipelineWorkspaceItem(
                    user_id=2,
                    item_id='news-001',
                    item_type='article',
                    action='favorite',
                    title='国家管网推进管道完整性管理数字化升级',
                    snapshot={'category': '管网安全', 'demo': True},
                    create_time=now - timedelta(hours=1),
                )
            )

        await db.commit()


if __name__ == '__main__':
    asyncio.run(seed())
    print('PipeSight 开发种子数据已就绪')
