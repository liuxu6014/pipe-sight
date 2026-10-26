from typing import Annotated

from fastapi import BackgroundTasks, File, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.infrastructure.schemas.files import UploadResponseModel
from app.infrastructure.services.file_transfer import FileTransferService
from app.infrastructure.services.logging_support import logger
from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.pre_auth import PreAuthDependency
from common.http.contracts import ApiNamespace
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DynamicResponseModel

common_controller = APIRouterPro(prefix='/common', order_num=16, tags=['通用模块'], dependencies=[PreAuthDependency()])


@common_controller.post(
    '/upload',
    summary='通用文件上传接口',
    description='用于上传文件',
    response_model=DynamicResponseModel[UploadResponseModel],
)
@ApiRateLimit(namespace=ApiNamespace.COMMON_UPLOAD, preset=ApiRateLimitPreset.COMMON_UPLOAD)
async def common_upload(request: Request, file: Annotated[UploadFile, File(...)]) -> Response:
    upload_result = await FileTransferService.upload_service(str(request.base_url), file)
    logger.info('上传成功')

    return ResponseUtil.success(model_content=upload_result.result)


@common_controller.get(
    '/download',
    summary='通用文件下载接口',
    description='用于下载下载目录中的文件',
    response_class=StreamingResponse,
    responses={
        200: {
            'description': '流式返回文件',
            'content': {
                'application/octet-stream': {},
            },
        }
    },
)
async def common_download(
    request: Request,
    background_tasks: BackgroundTasks,
    file_name: Annotated[str, Query(alias='fileName')],
    delete: Annotated[bool, Query()],
) -> Response:
    download_result = await FileTransferService.download_services(background_tasks, file_name, delete)
    logger.info(download_result.message)

    return ResponseUtil.streaming(data=download_result.result)


@common_controller.get(
    '/download/resource',
    summary='通用资源文件下载接口',
    description='用于下载上传目录中的资源文件',
    response_class=StreamingResponse,
    responses={
        200: {
            'description': '流式返回文件',
            'content': {
                'application/octet-stream': {},
            },
        }
    },
)
async def common_download_resource(request: Request, resource: Annotated[str, Query()]) -> Response:
    download_resource_result = await FileTransferService.download_resource_services(resource)
    logger.info(download_resource_result.message)

    return ResponseUtil.streaming(data=download_resource_result.result)
