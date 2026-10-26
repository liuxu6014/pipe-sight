"""服务器运行监控 API。"""

from fastapi import Request, Response

from app.infrastructure.schemas.server import ServerMonitorModel
from app.infrastructure.services.logging_support import logger
from app.infrastructure.services.server import ServerService
from common.annotation.cache_annotation import ApiCache
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.http.contracts import ApiNamespace
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel

server_controller = APIRouterPro(
    prefix='/monitor/server', order_num=14, tags=['系统监控-服务监控'], dependencies=[PreAuthDependency()]
)


@server_controller.get(
    '',
    summary='获取服务器监控信息接口',
    description='用于获取当前服务器的监控信息',
    response_model=DataResponseModel[ServerMonitorModel],
    dependencies=[UserInterfaceAuthDependency('monitor:server:list')],
)
@ApiCache(namespace=ApiNamespace.MONITOR_SERVER_INFO)
async def get_monitor_server_info(request: Request) -> Response:
    result = await ServerService.get_server_monitor_info()
    logger.info('获取成功')
    return ResponseUtil.success(data=result)


__all__ = ['server_controller']
