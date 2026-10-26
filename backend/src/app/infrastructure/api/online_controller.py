"""在线会话监控 API。"""

from typing import Annotated

from fastapi import Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.schemas.online import DeleteOnlineModel, OnlinePageResponseModel, OnlineQueryModel
from app.infrastructure.services.logging_support import logger
from app.infrastructure.services.online import OnlineService
from common.annotation.log_annotation import Log
from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.enums.audit import BusinessType
from common.http.contracts import ApiNamespace
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import ResponseBaseModel

online_controller = APIRouterPro(
    prefix='/monitor/online', order_num=12, tags=['系统监控-在线用户'], dependencies=[PreAuthDependency()]
)


@online_controller.get(
    '/list',
    summary='获取在线用户分页列表接口',
    description='用于获取在线用户分页列表',
    response_model=OnlinePageResponseModel,
    dependencies=[UserInterfaceAuthDependency('monitor:online:list')],
)
async def get_monitor_online_list(
    request: Request,
    online_page_query: Annotated[OnlineQueryModel, Query()],
) -> Response:
    online_query_result = await OnlineService.get_online_list_services(request.app.state.redis, online_page_query)
    logger.info('获取成功')

    return ResponseUtil.success(
        model_content=OnlinePageResponseModel(rows=online_query_result, total=len(online_query_result))
    )


@online_controller.delete(
    '/{token_ids}',
    summary='强退在线用户接口',
    description='用于强退指定会话编号的在线用户',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('monitor:online:forceLogout')],
)
@ApiRateLimit(namespace=ApiNamespace.MONITOR_ONLINE_FORCE_LOGOUT, preset=ApiRateLimitPreset.USER_SECURITY_MUTATION)
@Log(title='在线用户', business_type=BusinessType.FORCE)
async def delete_monitor_online(
    request: Request,
    token_ids: Annotated[str, Path(description='需要强退的会话编号')],
    query_db: Annotated[AsyncSession, DBSessionDependency()],
) -> Response:
    delete_online = DeleteOnlineModel(tokenIds=token_ids)
    delete_online_result = await OnlineService.delete_online_services(request.app.state.redis, delete_online)
    logger.info(delete_online_result.message)

    return ResponseUtil.success(msg=delete_online_result.message)


__all__ = ['online_controller']
