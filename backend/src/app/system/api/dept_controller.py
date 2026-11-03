from datetime import datetime
from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.system.models.dept import SysDept
from app.system.schemas.dept import DeleteDeptModel, DeptModel, DeptQueryModel
from app.system.schemas.user import CurrentUserModel
from app.system.services.depts import DeptService
from common.annotation.cache_annotation import ApiCacheEvict
from common.annotation.log_annotation import Log
from common.aspect.data_scope import DataScopeDependency
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency
from common.enums.audit import BusinessType
from common.http.contracts import ApiGroup
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel, ResponseBaseModel

dept_controller = APIRouterPro(
    prefix='/system/dept',
    order_num=6,
    tags=['系统管理-部门管理'],
    dependencies=[PreAuthDependency()],
)


@dept_controller.get(
    '/list/exclude/{dept_id}',
    summary='获取编辑部门的下拉树接口',
    response_model=DataResponseModel[list[DeptModel]],
    dependencies=[UserInterfaceAuthDependency('system:dept:list')],
)
async def get_system_dept_tree_for_edit_option(
    request: Request,
    dept_id: Annotated[int, Path(gt=0)],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    result = await DeptService.get_dept_for_edit_option_services(query_db, DeptModel(deptId=dept_id), data_scope_sql)
    return ResponseUtil.success(data=result)


@dept_controller.get(
    '/list',
    summary='获取部门列表接口',
    response_model=DataResponseModel[list[DeptModel]],
    dependencies=[UserInterfaceAuthDependency('system:dept:list')],
)
async def get_system_dept_list(
    request: Request,
    dept_query: Annotated[DeptQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    result = await DeptService.get_dept_list_services(query_db, dept_query, data_scope_sql)
    return ResponseUtil.success(data=result)


@dept_controller.post(
    '',
    summary='新增部门接口',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('system:dept:add')],
)
@ApiCacheEvict(namespaces=ApiGroup.USER_INFO_MUTATION)
@Log(title='部门管理', business_type=BusinessType.INSERT)
async def add_system_dept(
    request: Request,
    add_dept: DeptModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    add_dept.create_by = add_dept.update_by = current_user.user.user_name
    add_dept.create_time = add_dept.update_time = datetime.now()
    result = await DeptService.add_dept_services(query_db, add_dept, data_scope_sql)
    return ResponseUtil.success(msg=result.message)


@dept_controller.put(
    '',
    summary='编辑部门接口',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('system:dept:edit')],
)
@ApiCacheEvict(namespaces=ApiGroup.USER_INFO_MUTATION)
@Log(title='部门管理', business_type=BusinessType.UPDATE)
async def edit_system_dept(
    request: Request,
    edit_dept: DeptModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    edit_dept.update_by = current_user.user.user_name
    edit_dept.update_time = datetime.now()
    result = await DeptService.edit_dept_services(query_db, edit_dept, data_scope_sql)
    return ResponseUtil.success(msg=result.message)


@dept_controller.delete(
    '/{dept_ids}',
    summary='删除部门接口',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('system:dept:remove')],
)
@ApiCacheEvict(namespaces=ApiGroup.USER_INFO_MUTATION)
@Log(title='部门管理', business_type=BusinessType.DELETE)
async def delete_system_dept(
    request: Request,
    dept_ids: str,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    result = await DeptService.delete_dept_services(
        query_db,
        DeleteDeptModel(
            deptIds=dept_ids,
            updateBy=current_user.user.user_name,
            updateTime=datetime.now(),
        ),
        data_scope_sql,
    )
    return ResponseUtil.success(msg=result.message)


@dept_controller.get(
    '/{dept_id}',
    summary='获取部门详情接口',
    response_model=DataResponseModel[DeptModel],
    dependencies=[UserInterfaceAuthDependency('system:dept:query')],
)
async def query_detail_system_dept(
    request: Request,
    dept_id: Annotated[int, Path(gt=0)],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    data_scope_sql: Annotated[ColumnElement, DataScopeDependency(SysDept, user_alias=None)],
) -> Response:
    result = await DeptService.dept_detail_services(query_db, dept_id, data_scope_sql)
    return ResponseUtil.success(data=result)
