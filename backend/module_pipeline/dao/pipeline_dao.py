from collections.abc import Sequence

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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


class PipelineDao:
    """管网用户端业务数据访问层。"""

    @classmethod
    async def list_sources(cls, db: AsyncSession) -> Sequence[PipelineSource]:
        return (
            (
                await db.execute(
                    select(PipelineSource).order_by(PipelineSource.enabled.desc(), PipelineSource.name.asc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_source(cls, db: AsyncSession, source_id: str) -> PipelineSource | None:
        return (
            (await db.execute(select(PipelineSource).where(PipelineSource.source_id == source_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def list_collection_runs(cls, db: AsyncSession) -> Sequence[PipelineCrawlRun]:
        return (
            (await db.execute(select(PipelineCrawlRun).order_by(PipelineCrawlRun.create_time.desc())))
            .scalars()
            .all()
        )

    @classmethod
    async def get_collection_run(cls, db: AsyncSession, run_id: str) -> PipelineCrawlRun | None:
        return (
            (await db.execute(select(PipelineCrawlRun).where(PipelineCrawlRun.run_id == run_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def list_pending_handoff_runs(
        cls,
        db: AsyncSession,
        *,
        limit: int = 50,
    ) -> Sequence[PipelineCrawlRun]:
        return (
            (
                await db.execute(
                    select(PipelineCrawlRun)
                    .where(PipelineCrawlRun.handoff_status.in_(['dispatched', 'processing', 'partial']))
                    .order_by(PipelineCrawlRun.handoff_time.asc(), PipelineCrawlRun.create_time.asc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def add_collection_run(cls, db: AsyncSession, run: PipelineCrawlRun) -> PipelineCrawlRun:
        db.add(run)
        await db.flush()
        return run

    @classmethod
    async def list_handoff_articles(
        cls,
        db: AsyncSession,
        *,
        run_id: str | None = None,
        limit: int = 500,
        include_completed: bool = False,
    ) -> Sequence[PipelineArticle]:
        query = select(PipelineArticle)
        if include_completed:
            query = query.where(PipelineArticle.handoff_record_id.is_not(None))
        else:
            query = query.where(
                PipelineArticle.handoff_status.in_(['pending', 'dispatched', 'processing', 'partial', 'failed'])
            )
        if run_id:
            query = query.where(PipelineArticle.collection_run_id == run_id)
        return (
            (await db.execute(query.order_by(PipelineArticle.update_time.asc()).limit(limit)))
            .scalars()
            .all()
        )

    @classmethod
    async def list_articles(
        cls,
        db: AsyncSession,
        *,
        article_type: str | None = None,
        keyword: str | None = None,
    ) -> Sequence[PipelineArticle]:
        query = select(PipelineArticle)
        if article_type:
            query = query.where(PipelineArticle.article_type == article_type)
        if keyword:
            pattern = f'%{keyword}%'
            query = query.where(
                or_(
                    PipelineArticle.title.ilike(pattern),
                    PipelineArticle.summary.ilike(pattern),
                    PipelineArticle.body.ilike(pattern),
                )
            )
        return (
            (await db.execute(query.order_by(PipelineArticle.published_time.desc(), PipelineArticle.create_time.desc())))
            .scalars()
            .all()
        )

    @classmethod
    async def list_papers(cls, db: AsyncSession, *, keyword: str | None = None) -> Sequence[PipelinePaper]:
        query = select(PipelinePaper)
        if keyword:
            pattern = f'%{keyword}%'
            query = query.where(
                or_(
                    PipelinePaper.title.ilike(pattern),
                    PipelinePaper.abstract_text.ilike(pattern),
                    PipelinePaper.authors.ilike(pattern),
                )
            )
        return (
            (await db.execute(query.order_by(PipelinePaper.publication_year.desc(), PipelinePaper.create_time.desc())))
            .scalars()
            .all()
        )

    @classmethod
    async def get_article(cls, db: AsyncSession, article_id: str) -> PipelineArticle | None:
        return (
            (await db.execute(select(PipelineArticle).where(PipelineArticle.article_id == article_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def get_paper(cls, db: AsyncSession, paper_id: str) -> PipelinePaper | None:
        return (
            (await db.execute(select(PipelinePaper).where(PipelinePaper.paper_id == paper_id)))
            .scalars()
            .first()
        )

    @classmethod
    async def list_accessible_materials(
        cls,
        db: AsyncSession,
        user_id: int,
    ) -> Sequence[PipelineMaterial]:
        # 产品只区分普通用户和管理员，不按部门切分数据；user_id=1 为管理员。
        scope_filter = or_(
            PipelineMaterial.owner_id == user_id,
            user_id == 1,
            PipelineMaterial.permission_scope == 'public',
        )
        return (
            (
                await db.execute(
                    select(PipelineMaterial).where(scope_filter).order_by(PipelineMaterial.update_time.desc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_accessible_material(
        cls,
        db: AsyncSession,
        material_id: str,
        user_id: int,
    ) -> PipelineMaterial | None:
        rows = await cls.list_accessible_materials(db, user_id)
        return next((item for item in rows if item.file_id == material_id), None)

    @classmethod
    async def get_owned_material(
        cls,
        db: AsyncSession,
        material_id: str,
        user_id: int,
    ) -> PipelineMaterial | None:
        return (
            (
                await db.execute(
                    select(PipelineMaterial).where(
                        PipelineMaterial.file_id == material_id,
                        PipelineMaterial.owner_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_material(cls, db: AsyncSession, material: PipelineMaterial) -> PipelineMaterial:
        db.add(material)
        await db.flush()
        return material

    @classmethod
    async def delete_material(cls, db: AsyncSession, material_id: str, user_id: int) -> None:
        await db.execute(
            delete(PipelineWorkspaceItem).where(
                PipelineWorkspaceItem.item_id == material_id,
                PipelineWorkspaceItem.item_type == 'material',
            )
        )
        await db.execute(
            delete(PipelineMaterial).where(
                PipelineMaterial.file_id == material_id,
                PipelineMaterial.owner_id == user_id,
            )
        )

    @classmethod
    async def list_workspace_items(cls, db: AsyncSession, user_id: int) -> Sequence[PipelineWorkspaceItem]:
        return (
            (
                await db.execute(
                    select(PipelineWorkspaceItem)
                    .where(PipelineWorkspaceItem.user_id == user_id)
                    .order_by(PipelineWorkspaceItem.create_time.desc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_workspace_item(
        cls,
        db: AsyncSession,
        user_id: int,
        item_type: str,
        item_id: str,
        action: str,
    ) -> PipelineWorkspaceItem | None:
        return (
            (
                await db.execute(
                    select(PipelineWorkspaceItem).where(
                        PipelineWorkspaceItem.user_id == user_id,
                        PipelineWorkspaceItem.item_type == item_type,
                        PipelineWorkspaceItem.item_id == item_id,
                        PipelineWorkspaceItem.action == action,
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_workspace_item(
        cls,
        db: AsyncSession,
        workspace_item: PipelineWorkspaceItem,
    ) -> PipelineWorkspaceItem:
        db.add(workspace_item)
        await db.flush()
        return workspace_item

    @classmethod
    async def delete_workspace_item(cls, db: AsyncSession, user_id: int, item_id: str, action: str) -> None:
        await db.execute(
            delete(PipelineWorkspaceItem).where(
                PipelineWorkspaceItem.user_id == user_id,
                PipelineWorkspaceItem.item_id == item_id,
                PipelineWorkspaceItem.action == action,
            )
        )

    @classmethod
    async def add_research_job(cls, db: AsyncSession, job: PipelineResearchJob) -> PipelineResearchJob:
        db.add(job)
        await db.flush()
        return job

    @classmethod
    async def list_research_jobs(cls, db: AsyncSession, user_id: int) -> Sequence[PipelineResearchJob]:
        return (
            (
                await db.execute(
                    select(PipelineResearchJob)
                    .where(PipelineResearchJob.user_id == user_id)
                    .order_by(PipelineResearchJob.update_time.desc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_research_job(cls, db: AsyncSession, job_id: str, user_id: int) -> PipelineResearchJob | None:
        return (
            (
                await db.execute(
                    select(PipelineResearchJob).where(
                        PipelineResearchJob.task_id == job_id,
                        PipelineResearchJob.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def add_report(cls, db: AsyncSession, report: PipelineReport) -> PipelineReport:
        db.add(report)
        await db.flush()
        return report

    @classmethod
    async def list_reports(cls, db: AsyncSession, user_id: int) -> Sequence[PipelineReport]:
        return (
            (
                await db.execute(
                    select(PipelineReport)
                    .where(PipelineReport.user_id == user_id)
                    .order_by(PipelineReport.update_time.desc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_report(cls, db: AsyncSession, report_id: str, user_id: int) -> PipelineReport | None:
        return (
            (
                await db.execute(
                    select(PipelineReport).where(
                        PipelineReport.report_id == report_id,
                        PipelineReport.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def get_report_by_task(
        cls,
        db: AsyncSession,
        task_id: str,
        user_id: int,
    ) -> PipelineReport | None:
        return (
            (
                await db.execute(
                    select(PipelineReport).where(
                        PipelineReport.source_task_id == task_id,
                        PipelineReport.user_id == user_id,
                    )
                )
            )
            .scalars()
            .first()
        )

    @classmethod
    async def list_reports_by_tasks(
        cls,
        db: AsyncSession,
        task_ids: list[str],
        user_id: int,
    ) -> Sequence[PipelineReport]:
        if not task_ids:
            return []
        return (
            (
                await db.execute(
                    select(PipelineReport).where(
                        PipelineReport.source_task_id.in_(task_ids),
                        PipelineReport.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def add_report_version(
        cls,
        db: AsyncSession,
        report_version: PipelineReportVersion,
    ) -> PipelineReportVersion:
        db.add(report_version)
        await db.flush()
        return report_version

    @classmethod
    async def list_report_versions(
        cls,
        db: AsyncSession,
        report_id: str,
    ) -> Sequence[PipelineReportVersion]:
        return (
            (
                await db.execute(
                    select(PipelineReportVersion)
                    .where(PipelineReportVersion.report_id == report_id)
                    .order_by(PipelineReportVersion.version_no.desc())
                )
            )
            .scalars()
            .all()
        )

    @classmethod
    async def get_report_version(
        cls,
        db: AsyncSession,
        report_id: str,
        version_no: int,
    ) -> PipelineReportVersion | None:
        return (
            (
                await db.execute(
                    select(PipelineReportVersion).where(
                        PipelineReportVersion.report_id == report_id,
                        PipelineReportVersion.version_no == version_no,
                    )
                )
            )
            .scalars()
            .first()
        )
