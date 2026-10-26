"""论文生成兼容接口，内部统一走科研任务和报告服务。"""

from typing import Annotated

from fastapi import Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.schemas.pipeline import BusinessId
from app.research.schemas.manuscript import (
    ManuscriptExportModel,
    ManuscriptGenerateModel,
    ManuscriptJobModel,
    ManuscriptListModel,
    ManuscriptTitleSuggestModel,
    ManuscriptTitleSuggestResultModel,
)
from app.research.services.manuscript import ManuscriptApiService
from app.system.api.dependencies import CurrentUserDependency, CurrentUserModel, PreAuthDependency
from common.aspect.db_seesion import DBSessionDependency
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel

manuscript_controller = APIRouterPro(
    prefix='/manuscript',
    order_num=31,
    tags=['论文生成'],
    dependencies=[PreAuthDependency()],
)


@manuscript_controller.post('/generate', summary='生成论文草稿', response_model=DataResponseModel[ManuscriptJobModel])
async def generate_manuscript(
    request: Request,
    body: ManuscriptGenerateModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ManuscriptApiService.queue(
        query_db,
        current_user.user.user_id,
        current_user.user.nick_name or current_user.user.user_name,
        body,
    )
    return ResponseUtil.success(data=data, msg='论文任务已进入后台生成队列')


@manuscript_controller.get('/jobs', summary='查询论文生成任务', response_model=DataResponseModel[ManuscriptListModel])
async def list_manuscript_jobs(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    keyword: Annotated[str | None, Query(description='关键词')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    page_num: Annotated[int, Query(alias='pageNum', ge=1)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=1, le=100)] = 10,
) -> Response:
    data = await ManuscriptApiService.list(query_db, current_user.user.user_id, keyword, status, page_num, page_size)
    return ResponseUtil.success(data=data)


@manuscript_controller.get(
    '/jobs/{job_id}', summary='获取论文生成任务详情', response_model=DataResponseModel[ManuscriptJobModel]
)
async def get_manuscript_job(
    request: Request,
    job_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ManuscriptApiService.get(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data)


@manuscript_controller.get(
    '/jobs/{job_id}/export',
    summary='导出论文Markdown',
    response_model=DataResponseModel[ManuscriptExportModel],
)
async def export_manuscript_job(
    request: Request,
    job_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await ManuscriptApiService.export(query_db, current_user.user.user_id, job_id)
    return ResponseUtil.success(data=data)


@manuscript_controller.post(
    '/titles/suggest',
    summary='生成论文候选标题',
    response_model=DataResponseModel[ManuscriptTitleSuggestResultModel],
)
async def suggest_manuscript_titles(request: Request, body: ManuscriptTitleSuggestModel) -> Response:
    return ResponseUtil.success(data={'titles': ManuscriptApiService.suggest_titles(body.description, body.keywords)})
