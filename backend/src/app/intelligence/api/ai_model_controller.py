"""统一文本/图片模型管理 API；全局配置采用管理员/接口权限。"""

from typing import Annotated, Literal

from fastapi import HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.schemas.ai_model import (
    AiModelModel,
    AiModelPageQueryModel,
    DeleteAiModelModel,
    TranslationModelSelection,
)
from app.intelligence.services.ai_model_service import AiModelService
from app.intelligence.services.translation_settings import (
    generation_settings,
    processing_settings,
    save_generation_settings,
    save_processing_settings,
    save_translation_settings,
    translation_settings,
)
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


@ai_model_controller.get('/translation-config', dependencies=[UserInterfaceAuthDependency('ai:model:query')])
async def get_translation_config(
    request: Request, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    try:
        return ResponseUtil.success(data=await translation_settings(query_db))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='翻译模型配置无效，请重新设置') from exc


@ai_model_controller.put('/translation-config', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def put_translation_config(
    request: Request, payload: TranslationModelSelection, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    try:
        return ResponseUtil.success(
            data=await save_translation_settings(query_db, payload.model_id), msg='翻译模型已更新'
        )
    except ValueError as exc:
        await query_db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@ai_model_controller.get('/processing-config', dependencies=[UserInterfaceAuthDependency('ai:model:query')])
async def get_processing_config(request: Request, query_db: Annotated[AsyncSession, DBSessionDependency()]) -> Response:
    try:
        return ResponseUtil.success(data=await processing_settings(query_db))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='内容处理模型配置无效，请重新设置') from exc


@ai_model_controller.put('/processing-config', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def put_processing_config(
    request: Request, payload: TranslationModelSelection, query_db: Annotated[AsyncSession, DBSessionDependency()]
) -> Response:
    try:
        return ResponseUtil.success(
            data=await save_processing_settings(query_db, payload.model_id), msg='内容处理模型已更新'
        )
    except ValueError as exc:
        await query_db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@ai_model_controller.get('/purpose-config/{purpose}', dependencies=[UserInterfaceAuthDependency('ai:model:query')])
async def get_generation_config(
    request: Request,
    purpose: Literal['image', 'digest', 'research'],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    try:
        return ResponseUtil.success(data=await generation_settings(query_db, purpose))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail='生成模型配置无效，请重新设置') from exc


@ai_model_controller.put('/purpose-config/{purpose}', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def put_generation_config(
    request: Request,
    purpose: Literal['image', 'digest', 'research'],
    payload: TranslationModelSelection,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    try:
        return ResponseUtil.success(
            data=await save_generation_settings(query_db, purpose, payload.model_id), msg='生成模型已更新'
        )
    except ValueError as exc:
        await query_db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
