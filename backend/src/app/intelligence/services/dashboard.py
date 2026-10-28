"""Compact administrator totals, using actual categories and collection status."""

from sqlalchemy import func, select

from app.business_ids import wire_id
from app.intelligence.models.collection import PipelineCrawlRun, PipelineSource
from app.intelligence.models.content import PipelineArticle, PipelineCategory, PipelinePaper
from app.library.models.materials import PipelineMaterial


class IntelligenceDashboardService:
    @staticmethod
    async def summary(db, *, date_formatter):
        async def count(model, *conditions):
            return (await db.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one()

        groups = []
        for model in (PipelineArticle, PipelinePaper):
            groups.extend(
                (
                    await db.execute(
                        select(PipelineCategory.name, func.count())
                        .join(model, model.category_id == PipelineCategory.id)
                        .group_by(PipelineCategory.name)
                    )
                ).all()
            )
        totals = {}
        for name, value in groups:
            totals[name] = totals.get(name, 0) + value
        runs = (
            (await db.execute(
                select(PipelineCrawlRun, PipelineSource.name)
                .outerjoin(PipelineSource, PipelineSource.id == PipelineCrawlRun.source_id)
                .order_by(PipelineCrawlRun.created_at.desc(), PipelineCrawlRun.id.desc()).limit(10)
            ))
            .all()
        )
        return {
            'metrics': [
                {'label': '新闻资讯', 'value': await count(PipelineArticle), 'unit': '条'},
                {'label': '论文资料', 'value': await count(PipelinePaper), 'unit': '篇'},
                {
                    'label': '已解析资料',
                    'value': await count(PipelineMaterial, PipelineMaterial.status == 'ready'),
                    'unit': '份',
                },
            ],
            'collect_status': [
                {
                    'id': wire_id(run.id),
                    'name': source_name or '来源名称未提供',
                    'status': run.status,
                    'fetched_count': run.fetched_count,
                    'saved_count': run.saved_count,
                    'failed_count': run.failed_count,
                }
                for run, source_name in runs
            ],
            'hot_topics': [
                {'name': name, 'count': value}
                for name, value in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:6]
            ],
        }
