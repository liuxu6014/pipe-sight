from datetime import datetime, time
from typing import Any

from sqlalchemy import asc, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.audit import SysLogininfor, SysOperLog
from app.infrastructure.schemas.log import (
    LogininforModel,
    LoginLogPageQueryModel,
    OperLogModel,
    OperLogPageQueryModel,
)
from app.infrastructure.services.datetime_formatting import DateTimeFormatter
from app.infrastructure.services.pagination import PaginationService
from app.infrastructure.services.persistence_mapping import PersistenceMapping
from app.infrastructure.services.serialization import SnakeCaseUtil
from common.http.schemas import PageModel


class OperationLogDao:
    """
    操作日志管理模块数据库操作层
    """

    @classmethod
    async def get_operation_log_list(
        cls, db: AsyncSession, query_object: OperLogPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取操作日志列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 操作日志列表信息对象
        """
        if query_object.is_asc == 'ascending':
            order_by_column = asc(
                PersistenceMapping.column(SysOperLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column))
            )
        elif query_object.is_asc == 'descending':
            order_by_column = desc(
                PersistenceMapping.column(SysOperLog, SnakeCaseUtil.camel_to_snake(query_object.order_by_column))
            )
        else:
            order_by_column = desc(SysOperLog.operated_at)
        query = (
            select(SysOperLog)
            .where(
                SysOperLog.title.like(f'%{query_object.title}%') if query_object.title else True,
                SysOperLog.username.like(f'%{query_object.oper_name}%') if query_object.oper_name else True,
                SysOperLog.business_type == query_object.business_type if query_object.business_type else True,
                SysOperLog.status == query_object.status if query_object.status else True,
                SysOperLog.operated_at.between(
                    datetime.combine(DateTimeFormatter.parse_date(query_object.begin_time), time(00, 00, 00)),
                    datetime.combine(DateTimeFormatter.parse_date(query_object.end_time), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .distinct()
            .order_by(order_by_column)
        )
        operation_log_list: PageModel | list[dict[str, Any]] = await PaginationService.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

        return operation_log_list

    @classmethod
    async def add_operation_log_dao(cls, db: AsyncSession, operation_log: OperLogModel) -> SysOperLog:
        """
        新增操作日志数据库操作

        :param db: orm对象
        :param operation_log: 操作日志对象
        :return: 新增校验结果
        """
        db_operation_log = SysOperLog(**PersistenceMapping.to_record(SysOperLog, operation_log.model_dump()))
        db.add(db_operation_log)
        await db.flush()

        return db_operation_log

    @classmethod
    async def delete_operation_log_dao(cls, db: AsyncSession, operation_log: OperLogModel) -> None:
        """
        删除操作日志数据库操作

        :param db: orm对象
        :param operation_log: 操作日志对象
        :return:
        """
        await db.execute(delete(SysOperLog).where(SysOperLog.id.in_([operation_log.oper_id])))

    @classmethod
    async def clear_operation_log_dao(cls, db: AsyncSession) -> None:
        """
        清除操作日志数据库操作

        :param db: orm对象
        :return:
        """
        await db.execute(delete(SysOperLog))


class LoginLogDao:
    """
    登录日志管理模块数据库操作层
    """

    @classmethod
    async def get_login_log_list(
        cls, db: AsyncSession, query_object: LoginLogPageQueryModel, is_page: bool = False
    ) -> PageModel | list[dict[str, Any]]:
        """
        根据查询参数获取登录日志列表信息

        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 登录日志列表信息对象
        """
        if query_object.is_asc == 'ascending':
            order_by_column = asc(
                PersistenceMapping.column(SysLogininfor, SnakeCaseUtil.camel_to_snake(query_object.order_by_column))
            )
        elif query_object.is_asc == 'descending':
            order_by_column = desc(
                PersistenceMapping.column(SysLogininfor, SnakeCaseUtil.camel_to_snake(query_object.order_by_column))
            )
        else:
            order_by_column = desc(SysLogininfor.logged_at)
        query = (
            select(SysLogininfor)
            .where(
                SysLogininfor.ip.like(f'%{query_object.ipaddr}%') if query_object.ipaddr else True,
                SysLogininfor.username.like(f'%{query_object.user_name}%') if query_object.user_name else True,
                SysLogininfor.status == query_object.status if query_object.status else True,
                SysLogininfor.logged_at.between(
                    datetime.combine(DateTimeFormatter.parse_date(query_object.begin_time), time(00, 00, 00)),
                    datetime.combine(DateTimeFormatter.parse_date(query_object.end_time), time(23, 59, 59)),
                )
                if query_object.begin_time and query_object.end_time
                else True,
            )
            .distinct()
            .order_by(order_by_column)
        )
        login_log_list: PageModel | list[dict[str, Any]] = await PaginationService.paginate(
            db, query, query_object.page_num, query_object.page_size, is_page
        )

        return login_log_list

    @classmethod
    async def add_login_log_dao(cls, db: AsyncSession, login_log: LogininforModel) -> SysLogininfor:
        """
        新增登录日志数据库操作

        :param db: orm对象
        :param login_log: 登录日志对象
        :return: 新增校验结果
        """
        db_login_log = SysLogininfor(**PersistenceMapping.to_record(SysLogininfor, login_log.model_dump()))
        db.add(db_login_log)
        await db.flush()

        return db_login_log

    @classmethod
    async def delete_login_log_dao(cls, db: AsyncSession, login_log: LogininforModel) -> None:
        """
        删除登录日志数据库操作

        :param db: orm对象
        :param login_log: 登录日志对象
        :return:
        """
        await db.execute(delete(SysLogininfor).where(SysLogininfor.id.in_([login_log.info_id])))

    @classmethod
    async def clear_login_log_dao(cls, db: AsyncSession) -> None:
        """
        清除登录日志数据库操作

        :param db: orm对象
        :return:
        """
        await db.execute(delete(SysLogininfor))
