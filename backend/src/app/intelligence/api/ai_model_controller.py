"""统一文本/图片模型管理 API；全局配置采用管理员/接口权限。"""

from typing import Annotated, Literal

from fastapi import Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.schemas.ai_model import AiModelModel, AiModelPageQueryModel, DeleteAiModelModel
from app.intelligence.services.ai_model_service import AiModelService
from app.system.api.dependencies import PreAuthDependency
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import RoleInterfaceAuthDependency, UserInterfaceAuthDependency
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro

ai_model_controller = APIRouterPro(
    prefix='/ai/model',
    order_num=18,
    tags=['AI管理-模型管理'],
    dependencies=[PreAuthDependency(), RoleInterfaceAuthDependency('admin')],
)


@ai_model_controller.get('/list', dependencies=[UserInterfaceAuthDependency('ai:model:list')])
async def get_ai_model_list(
    request: Request,
    ai_model_page_query: Annotated[AiModelPageQueryModel, Query()],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    return ResponseUtil.success(
        model_content=await AiModelService.get_ai_model_list_services(query_db, ai_model_page_query, True, True)
    )


@ai_model_controller.get('/all', dependencies=[UserInterfaceAuthDependency('ai:model:query')])
async def get_ai_model_all(request: Request, query_db: Annotated[AsyncSession, DBSessionDependency()]) -> Response:
    return ResponseUtil.success(
        data=await AiModelService.get_ai_model_list_services(query_db, AiModelPageQueryModel(), True, False)
    )


@ai_model_controller.post('', dependencies=[UserInterfaceAuthDependency('ai:model:add')])
async def add_ai_model(
    request: Request, add_ai_model: AiModelModel, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    result = await AiModelService.add_ai_model_services(query_db, add_ai_model)
    return ResponseUtil.success(msg=result.message)


@ai_model_controller.put('', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def edit_ai_model(
    request: Request, edit_ai_model: AiModelModel, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    result = await AiModelService.edit_ai_model_services(query_db, edit_ai_model)
    return ResponseUtil.success(msg=result.message)


@ai_model_controller.delete('/{model_ids}', dependencies=[UserInterfaceAuthDependency('ai:model:remove')])
async def delete_ai_model(
    request: Request, model_ids: str, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    result = await AiModelService.delete_ai_model_services(query_db, DeleteAiModelModel(model_ids=model_ids))
    return ResponseUtil.success(msg=result.message)


@ai_model_controller.get('/{model_id}', dependencies=[UserInterfaceAuthDependency('ai:model:query')])
async def get_ai_model_detail(
    request: Request, model_id: int, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    return ResponseUtil.success(data=await AiModelService.ai_model_detail_services(query_db, model_id))


@ai_model_controller.post('/{model_id}/test', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def test_ai_model(
    request: Request,
    model_id: int,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    capability: Literal['text_generate', 'image_generate'] = 'text_generate',
) -> Response:
    # 仅用户主动点击才发起实际收费请求；本次离线验证不会执行此入口。
    result = await AiModelService.test_ai_model_services(query_db, model_id, True, capability)
    return ResponseUtil.success(msg=result.message, data=result)
