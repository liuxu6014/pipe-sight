"""资料库资料上传、解析和受控访问 API。"""

from typing import Annotated
from urllib.parse import quote

from fastapi import File, Form, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.services.file_storage import FileStorageService
from app.infrastructure.services.file_upload import FileUploadSupport
from app.intelligence.schemas.pipeline import BusinessId, PipelineListModel
from app.library.schemas.materials import MaterialEditModel
from app.library.services.materials import MaterialApiService, MaterialFileService
from app.system.api.dependencies import CurrentUserDependency, CurrentUserModel, PreAuthDependency
from common.aspect.db_seesion import DBSessionDependency
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel

controller = APIRouterPro(
    prefix='/pipeline',
    order_num=30,
    tags=['管网情报'],
    dependencies=[PreAuthDependency()],
)


@controller.get(
    '/knowledge/documents',
    summary='查询内部资料',
    response_model=DataResponseModel[PipelineListModel],
)
async def list_pipeline_knowledge_documents(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MaterialApiService.list_materials(query_db, current_user.user.user_id)
    return ResponseUtil.success(data=data)


@controller.post('/knowledge/documents', summary='上传内部资料')
async def upload_pipeline_knowledge_document(
    request: Request,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
    file: Annotated[UploadFile, File(...)],
    category: Annotated[str, Form()] = '内部文献',
    permission_scope: Annotated[str, Form(alias='permissionScope')] = 'private',
    tags: Annotated[str, Form()] = '',
) -> Response:
    stored = await FileStorageService.upload(
        str(request.base_url), file, max_bytes=MaterialFileService.max_source_bytes
    )
    owner_name = current_user.user.nick_name or current_user.user.user_name
    data = await MaterialApiService.create_material(
        query_db,
        user_id=current_user.user.user_id,
        owner_name=owner_name,
        name=stored.original_filename or file.filename or '未命名资料',
        category=category,
        permission_scope=permission_scope,
        file_name=stored.new_file_name,
        file_path=stored.file_name,
        file_url=stored.url,
        mime_type=file.content_type,
        file_size=stored.file_size,
        file_hash=stored.file_hash,
        # Let the guarded resolver map /profile to the upload root exactly once.
        local_path=stored.file_name,
        tags=[item.strip() for item in tags.split(',') if item.strip()],
    )
    return ResponseUtil.success(data=data, msg='已保存到资料库，解析状态单独更新')


@controller.put('/knowledge/documents/{material_id}', summary='编辑资料正文')
async def edit_pipeline_knowledge_document(
    material_id: BusinessId,
    body: MaterialEditModel,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MaterialApiService.edit(
        query_db,
        current_user.user.user_id,
        material_id,
        expected_version=body.expected_version,
        edited_text=body.edited_text,
        name=body.name,
    )
    return ResponseUtil.success(data=data)


@controller.get('/knowledge/documents/{material_id}', summary='获取知识库资料详情')
async def get_pipeline_knowledge_document(
    request: Request,
    material_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MaterialApiService.get_material(query_db, current_user.user.user_id, material_id)
    return ResponseUtil.success(data=data)


@controller.get(
    '/knowledge/documents/{material_id}/download',
    summary='受控下载知识库资料',
    response_class=StreamingResponse,
)
async def download_pipeline_knowledge_document(
    request: Request,
    material_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    file_path, file_name, media_type = await MaterialApiService.get_download(
        query_db,
        current_user.user.user_id,
        material_id,
    )
    return ResponseUtil.streaming(
        data=FileUploadSupport.generate_file(str(file_path)),
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(file_name)}"},
        media_type=media_type or 'application/octet-stream',
    )


@controller.post('/knowledge/documents/{material_id}/retry', summary='重新解析知识库资料')
async def retry_pipeline_knowledge_document(
    request: Request,
    material_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MaterialApiService.retry_parse(query_db, current_user.user.user_id, material_id)
    return ResponseUtil.success(data=data, msg='资料解析状态已更新')


@controller.delete('/knowledge/documents/{material_id}', summary='删除知识库资料')
async def delete_pipeline_knowledge_document(
    request: Request,
    material_id: BusinessId,
    query_db: Annotated[AsyncSession, DBSessionDependency()],
    current_user: Annotated[CurrentUserModel, CurrentUserDependency()],
) -> Response:
    data = await MaterialApiService.delete_material(query_db, current_user.user.user_id, material_id)
    return ResponseUtil.success(data=data, msg='资料已删除')
