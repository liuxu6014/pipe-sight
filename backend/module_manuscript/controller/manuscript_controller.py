from typing import Annotated

from fastapi import Query, Request, Response

from common.aspect.pre_auth import PreAuthDependency
from common.router import APIRouterPro
from common.vo import DataResponseModel
from module_manuscript.entity.vo.manuscript_vo import (
    ManuscriptExportModel,
    ManuscriptGenerateModel,
    ManuscriptJobModel,
    ManuscriptListModel,
    ManuscriptTitleSuggestModel,
    ManuscriptTitleSuggestResultModel,
)
from module_manuscript.service.manuscript_service import ManuscriptService
from utils.response_util import ResponseUtil

manuscript_controller = APIRouterPro(
    prefix='/manuscript',
    order_num=31,
    tags=['论文生成'],
    dependencies=[PreAuthDependency()],
)


@manuscript_controller.post('/generate', summary='生成论文草稿', response_model=DataResponseModel[ManuscriptJobModel])
async def generate_manuscript(request: Request, body: ManuscriptGenerateModel) -> Response:
    try:
        data = ManuscriptService.generate_manuscript(**body.model_dump())
        return ResponseUtil.success(data=data)
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@manuscript_controller.get('/jobs', summary='查询论文生成任务', response_model=DataResponseModel[ManuscriptListModel])
async def list_manuscript_jobs(
    request: Request,
    keyword: Annotated[str | None, Query(description='关键词')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    page_num: Annotated[int, Query(alias='pageNum', ge=1)] = 1,
    page_size: Annotated[int, Query(alias='pageSize', ge=1, le=100)] = 10,
) -> Response:
    return ResponseUtil.success(
        data=ManuscriptService.list_manuscripts(
            keyword=keyword,
            status=status,
            page_num=page_num,
            page_size=page_size,
        )
    )


@manuscript_controller.get('/jobs/{job_id}', summary='获取论文生成任务详情', response_model=DataResponseModel[ManuscriptJobModel])
async def get_manuscript_job(request: Request, job_id: str) -> Response:
    try:
        return ResponseUtil.success(data=ManuscriptService.get_manuscript(job_id))
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@manuscript_controller.get(
    '/jobs/{job_id}/export',
    summary='导出论文Markdown',
    response_model=DataResponseModel[ManuscriptExportModel],
)
async def export_manuscript_job(request: Request, job_id: str) -> Response:
    try:
        return ResponseUtil.success(data=ManuscriptService.export_manuscript(job_id))
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@manuscript_controller.post(
    '/titles/suggest',
    summary='生成论文候选标题',
    response_model=DataResponseModel[ManuscriptTitleSuggestResultModel],
)
async def suggest_manuscript_titles(request: Request, body: ManuscriptTitleSuggestModel) -> Response:
    return ResponseUtil.success(data={'titles': ManuscriptService.suggest_titles(body.description, body.keywords)})
