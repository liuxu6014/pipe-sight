"""研究专属 SQL；所有权限沿 reports.user_id，不依赖旧主 DAO。"""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_ids import parse_business_id
from app.intelligence.models.ai_models import AiModels
from app.intelligence.models.configuration import PipelineTemplateVersion as Template
from app.research.models.research_models import (
    PipelineDigestSchedule as Schedule,
)
from app.research.models.research_models import (
    PipelineReport as Report,
)
from app.research.models.research_models import (
    PipelineReportAsset as Asset,
)
from app.research.models.research_models import (
    PipelineReportVersion as Version,
)
from app.research.models.research_models import (
    PipelineResearchJob as Job,
)
from app.research.models.research_models import (
    PipelineWorkspaceItem as Basket,
)
from app.research.models.research_models import (
    utcnow,
)


class ResearchDao:
    @staticmethod
    async def add(db, item):
        db.add(item)
        await db.flush()
        return item

    add_report = add
    add_research_job = add
    add_report_version = add
    add_report_export = add
    add_workspace_item = add
    add_digest_schedule = add
    add_template = add

    @staticmethod
    async def get_report(db, report_id, user_id=None, *, lock=False):
        report_id = parse_business_id(report_id)
        query = select(Report).where(Report.id == report_id)
        if user_id is not None:
            query = query.where(Report.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return await db.scalar(query.execution_options(populate_existing=True))

    @staticmethod
    async def list_reports(db, user_id, **_):
        return list(
            await db.scalars(select(Report).where(Report.user_id == user_id).order_by(Report.updated_at.desc()))
        )

    @staticmethod
    async def list_admin_reports(db: AsyncSession) -> list[Report]:
        """Explicit read-only management query; personal and mutation queries stay owner scoped."""
        return list(await db.scalars(select(Report).order_by(Report.updated_at.desc(), Report.id.desc())))

    @staticmethod
    async def get_research_job(db, job_id, user_id=None, *, lock=False):
        job_id = parse_business_id(job_id)
        query = select(Job).join(Report, Report.id == Job.report_id).where(Job.id == job_id)
        if user_id is not None:
            query = query.where(Report.user_id == user_id)
        if lock:
            query = query.with_for_update(of=Job)
        return await db.scalar(query.execution_options(populate_existing=True))

    @staticmethod
    async def get_research_job_by_request_id(db, request_id, user_id=None):
        # 全局查找后由服务校验所有者和请求指纹；不得用用户过滤隐藏冲突。
        return await db.scalar(select(Job).where(Job.request_id == request_id))

    @staticmethod
    async def list_research_jobs(db, user_id):
        return list(
            await db.scalars(
                select(Job)
                .join(Report, Report.id == Job.report_id)
                .where(Report.user_id == user_id)
                .order_by(Job.created_at.desc())
            )
        )

    @staticmethod
    async def get_report_by_task(db, task_id, user_id):
        task_id = parse_business_id(task_id)
        return await db.scalar(
            select(Report).join(Job, Job.report_id == Report.id).where(Job.id == task_id, Report.user_id == user_id)
        )

    @classmethod
    async def claim_research_job(cls, db, job_id, user_id, *, worker_id='', lease_seconds=900, max_attempts=3):
        job = await cls.get_research_job(db, job_id, user_id, lock=True)
        now = utcnow()
        if not job or job.status not in {'queued', 'running'}:
            return None
        if job.status == 'running' and job.lease_expires_at and cls.aware(job.lease_expires_at) > now:
            return None
        if job.attempts >= max_attempts:
            job.status, job.error, job.finished_at = 'failed', '执行次数已达上限', now
            job.execution_token = job.lease_expires_at = None
            await db.commit()
            return None
        job.status = 'running'
        job.attempts += 1
        job.execution_token = uuid4().hex
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.started_at = job.started_at or now
        job.finished_at = None
        await db.commit()
        return job

    @staticmethod
    def aware(value):
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    @classmethod
    async def lock_running_research_job(cls, db, job_id, user_id, token):
        job = await cls.get_research_job(db, job_id, user_id, lock=True)
        if (
            not job
            or job.status != 'running'
            or job.execution_token != token
            or not job.lease_expires_at
            or cls.aware(job.lease_expires_at) <= utcnow()
        ):
            return None
        return job

    @classmethod
    async def touch_research_job(cls, db, job_id, user_id, *, execution_token, lease_seconds=900):
        job = await cls.lock_running_research_job(db, job_id, user_id, execution_token)
        if not job:
            return False
        job.lease_expires_at = utcnow() + timedelta(seconds=lease_seconds)
        await db.commit()
        return True

    @staticmethod
    async def list_research_job_ids_for_dispatch(db, *, now, max_attempts=3, schedule_ids=None):
        query = (select(Job.id, Report.user_id).join(Report, Report.id == Job.report_id)
                 .where(or_(Job.status == 'queued', (Job.status == 'running') & (Job.lease_expires_at <= now))))
        if schedule_ids is not None:
            query = query.where(Job.schedule_id.in_([parse_business_id(value) for value in schedule_ids]))
        rows = (
            await db.execute(
                query
            )
        ).all()
        return [(row[0], row[1], '') for row in rows]

    @staticmethod
    async def list_report_versions(db, report_id):
        report_id = parse_business_id(report_id)
        return list(
            await db.scalars(select(Version).where(Version.report_id == report_id).order_by(Version.version.desc()))
        )

    @staticmethod
    async def get_report_version(db, report_id, version):
        report_id = parse_business_id(report_id)
        return await db.scalar(select(Version).where(Version.report_id == report_id, Version.version == version))

    @staticmethod
    async def get_template(db, template_id):
        return await db.get(Template, parse_business_id(template_id)) if template_id is not None else None

    @staticmethod
    async def list_templates(db, purpose=None):
        query = select(Template).order_by(Template.updated_at.desc())
        if purpose:
            query = query.where(Template.purpose == purpose)
        return list(await db.scalars(query))

    @staticmethod
    async def get_model(db, model_id):
        return await db.get(AiModels, parse_business_id(model_id)) if model_id is not None else None

    @staticmethod
    async def get_asset(db, asset_id, user_id=None, *, lock=False):
        asset_id = parse_business_id(asset_id)
        query = select(Asset).join(Report, Report.id == Asset.report_id).where(Asset.id == asset_id)
        if user_id is not None:
            query = query.where(Report.user_id == user_id)
        if lock:
            query = query.with_for_update(of=Asset)
        return await db.scalar(query.execution_options(populate_existing=True))

    @staticmethod
    async def list_assets(db, report_id, asset_type=None):
        report_id = parse_business_id(report_id)
        query = select(Asset).where(Asset.report_id == report_id).order_by(Asset.created_at)
        if asset_type:
            query = query.where(Asset.type == asset_type)
        return list(await db.scalars(query))

    @staticmethod
    async def list_report_export_ids_for_dispatch(db, **_):
        return list(await db.scalars(select(Asset.id).where(Asset.status == 'queued')))

    @staticmethod
    async def list_workspace_items(db, user_id):
        return list(await db.scalars(select(Basket).where(Basket.user_id == user_id)))

    @staticmethod
    async def get_workspace_item(db, user_id, item_type, item_id, action):
        item_id = parse_business_id(item_id)
        field = {
            'article': Basket.article_id,
            'paper': Basket.paper_id,
            'file': Basket.file_id,
            'material': Basket.file_id,
            'report': Basket.report_id,
        }[item_type]
        return await db.scalar(
            select(Basket).where(Basket.user_id == user_id, field == item_id, Basket.action == action)
        )

    @staticmethod
    async def delete_workspace_item(db, user_id, item_id, action):
        item_id = parse_business_id(item_id)
        from sqlalchemy import delete

        await db.execute(
            delete(Basket).where(
                Basket.user_id == user_id,
                Basket.action == action,
                or_(
                    Basket.article_id == item_id,
                    Basket.paper_id == item_id,
                    Basket.file_id == item_id,
                    Basket.report_id == item_id,
                ),
            )
        )

    @staticmethod
    async def list_digest_schedules(db, user_id):
        return list(await db.scalars(select(Schedule).where(Schedule.user_id == user_id)))

    @staticmethod
    async def latest_schedule_jobs(db, user_id, schedule_ids):
        if not schedule_ids:
            return {}
        latest = (select(func.max(Job.id).label('id')).join(Report, Report.id == Job.report_id)
                  .join(Schedule, Schedule.id == Job.schedule_id)
                  .where(Schedule.user_id == user_id, Report.user_id == user_id,
                         Schedule.id.in_(schedule_ids)).group_by(Job.schedule_id).subquery())
        pairs = (await db.execute(select(Job, Report).join(latest, latest.c.id == Job.id)
                                 .join(Report, Report.id == Job.report_id))).all()
        return {job.schedule_id: (job, report) for job, report in pairs}

    @staticmethod
    async def lock_digest_schedule_for_update(db, schedule_id, user_id):
        schedule_id = parse_business_id(schedule_id)
        return await db.scalar(
            select(Schedule)
            .where(Schedule.id == schedule_id, Schedule.user_id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    @staticmethod
    async def list_due_schedules(db, now, schedule_ids=None):
        query = select(Schedule).where(Schedule.is_enabled.is_(True), Schedule.next_run_at <= now)
        if schedule_ids is not None:
            query = query.where(Schedule.id.in_([parse_business_id(value) for value in schedule_ids]))
        return list(
            await db.scalars(
                query.with_for_update(skip_locked=True)
            )
        )

    @staticmethod
    async def load_content(db, kind, item_id):
        # 跨域只读取规范内容实体；不经过旧查询的 approved/发布/分类层。
        from app.intelligence.models.content import PipelineArticle, PipelinePaper

        model = {'article': PipelineArticle, 'paper': PipelinePaper}[kind]
        return await db.get(model, parse_business_id(item_id))

    @staticmethod
    def candidate_query(start, end, config):
        from app.intelligence.models.collection import PipelineSource
        from app.intelligence.models.content import PipelineArticle, PipelineCategory

        query = (
            select(PipelineArticle)
            .join(PipelineSource, PipelineSource.id == PipelineArticle.source_id)
            .where(PipelineArticle.published_at >= start, PipelineArticle.published_at < end)
        )
        if config.get('source_types'):
            query = query.where(PipelineSource.type.in_(config['source_types']))
        if config.get('source_ids'):
            query = query.where(PipelineArticle.source_id.in_([parse_business_id(i) for i in config['source_ids']]))
        if config.get('category_ids'):
            query = query.where(PipelineArticle.category_id.in_([parse_business_id(i) for i in config['category_ids']]))
        if config.get('category_names'):
            query = query.where(
                PipelineArticle.category_id.in_(
                    select(PipelineCategory.id).where(PipelineCategory.name.in_(config['category_names']))
                )
            )
        keywords = list(dict.fromkeys(term.strip() for term in (config.get('keywords') or []) if term.strip()))
        if keywords:
            query = query.where(
                or_(
                    *(
                        or_(
                            PipelineArticle.title.contains(keyword, autoescape=True),
                            PipelineArticle.content.contains(keyword, autoescape=True),
                            PipelineArticle.content_zh.contains(keyword, autoescape=True),
                        )
                        for keyword in keywords
                    )
                )
            )
        return query

    @classmethod
    async def digest_candidates(cls, db, start, end, config):
        from app.intelligence.models.content import PipelineArticle

        query = cls.candidate_query(start, end, config)
        return list(await db.scalars(query.order_by(PipelineArticle.published_at.desc(), PipelineArticle.id)))

    @classmethod
    async def search_digest_candidates(cls, db, filters):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        from sqlalchemy import func
        from sqlalchemy.orm import load_only

        from app.intelligence.models.content import PipelineArticle

        zone = ZoneInfo('Asia/Shanghai')
        start = datetime.combine(filters.period[0], datetime.min.time(), zone)
        end = datetime.combine(filters.period[-1], datetime.min.time(), zone) + timedelta(days=1)
        config = {
            'source_types': [{'新闻网站': 'website', '微信公众号': 'wechat'}[s] for s in filters.sources],
            'keywords': filters.keywords,
            'category_names': filters.directions,
        }
        base = cls.candidate_query(start, end, config)
        title = func.lower(func.trim(func.regexp_replace(PipelineArticle.title, r'\s+', ' ', 'g')))
        ranked = base.with_only_columns(
            PipelineArticle.id.label('id'),
            func.row_number()
            .over(partition_by=title, order_by=(PipelineArticle.published_at.desc(), PipelineArticle.id))
            .label('rank'),
        ).subquery()
        total = await db.scalar(select(func.count()).select_from(ranked).where(ranked.c.rank == 1))
        query = (
            select(PipelineArticle)
            .join(ranked, ranked.c.id == PipelineArticle.id)
            .where(ranked.c.rank == 1)
            .order_by(PipelineArticle.published_at.desc(), PipelineArticle.id)
            .options(load_only(PipelineArticle.id, PipelineArticle.title, PipelineArticle.published_at))
            .limit(filters.page_size)
            .offset((filters.page_num - 1) * filters.page_size)
        )
        return list(await db.scalars(query)), int(total or 0)


PipelineDao = ResearchDao
