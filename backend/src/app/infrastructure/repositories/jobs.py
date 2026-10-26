from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.jobs import SysJob
from app.infrastructure.schemas.jobs import JobModel, JobPageQueryModel
from app.infrastructure.services.pagination import PaginationService
from app.infrastructure.services.persistence_mapping import PersistenceMapping
from common.http.schemas import PageModel


class JobDao:
    """
    定时任务管理模块数据库操作层
    """

    @classmethod
    async def get_job_detail_by_id(cls, db: AsyncSession, job_id: int) -> SysJob | None:
        """
        根据定时任务id获取定时任务详细信息

        :param db: orm对象
        :param job_id: 定时任务id
        :return: 定时任务信息对象
        """
        job_info = (await db.execute(select(SysJob).where(SysJob.id == job_id))).scalars().first()

        return job_info

    @classmethod
    async def get_job_detail_by_info(cls, db: AsyncSession, job: JobModel) -> SysJob | None:
        """
        根据定时任务参数获取定时任务信息

        :param db: orm对象
        :param job: 定时任务参数对象
        :return: 定时任务信息对象
        """
        job_info = (
            (
                await db.execute(
                    select(SysJob).where(
                        SysJob.name == job.job_name,
                        SysJob.group_key == job.job_group,
                        SysJob.executor == job.job_executor,
                        SysJob.invoke_target == job.invoke_target,
                        SysJob.args == job.job_args,
                        SysJob.kwargs == job.job_kwargs,
                        SysJob.cron_expression == job.cron_expression,
                    )
                )
            )
            .scalars()
            .first()
        )

        return job_info

    @classmethod
    async def get_job_list(
        cls, db: AsyncSession, query_object: JobPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取定时任务列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 定时任务列表信息对象
        """
        query = (
            select(SysJob)
            .where(
                SysJob.name.like(f'%{query_object.job_name}%') if query_object.job_name else True,
                SysJob.group_key == query_object.job_group if query_object.job_group else True,
                SysJob.status == query_object.status if query_object.status else True,
            )
            .order_by(SysJob.id)
            .distinct()
        )
        job_list: PageModel | list[dict[str, Any]] = await PaginationService.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

        return job_list

    @classmethod
    async def get_job_list_for_scheduler(cls, db: AsyncSession) -> Sequence[SysJob]:
        """
        获取定时任务列表信息

        :param db: orm对象
        :return: 定时任务列表信息对象
        """
        job_list = (await db.execute(select(SysJob).where(SysJob.status == '0').distinct())).scalars().all()

        return job_list

    @classmethod
    async def get_all_job_list_for_scheduler(cls, db: AsyncSession) -> Sequence[SysJob]:
        """
        获取全部定时任务列表信息

        :param db: orm对象
        :return: 定时任务列表信息对象
        """
        job_list = (await db.execute(select(SysJob).distinct())).scalars().all()

        return job_list

    @classmethod
    async def add_job_dao(cls, db: AsyncSession, job: JobModel) -> SysJob:
        """
        新增定时任务数据库操作

        :param db: orm对象
        :param job: 定时任务对象
        :return:
        """
        db_job = SysJob(**PersistenceMapping.to_record(SysJob, job.model_dump()))
        db.add(db_job)
        await db.flush()

        return db_job

    @classmethod
    async def edit_job_dao(cls, db: AsyncSession, job: dict, old_job: JobModel) -> None:
        """
        编辑定时任务数据库操作

        :param db: orm对象
        :param job: 需要更新的定时任务字典
        :param old_job: 原定时任务对象
        :return:
        """
        await db.execute(
            update(SysJob)
            .where(
                SysJob.id == old_job.job_id,
                SysJob.name == old_job.job_name,
                SysJob.group_key == old_job.job_group,
            )
            .values(**PersistenceMapping.to_record(SysJob, job))
        )

    @classmethod
    async def delete_job_dao(cls, db: AsyncSession, job: JobModel) -> None:
        """
        删除定时任务数据库操作

        :param db: orm对象
        :param job: 定时任务对象
        :return:
        """
        await db.execute(delete(SysJob).where(SysJob.id.in_([job.job_id])))
