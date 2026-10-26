"""Redis 缓存监控 API。"""

from typing import Annotated

from fastapi import Path, Request, Response

from app.infrastructure.schemas.cache import CacheInfoModel, CacheMonitorModel
from app.infrastructure.services.cache import CacheService
from app.infrastructure.services.logging_support import logger
from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from common.http.contracts import ApiNamespace
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DataResponseModel, ResponseBaseModel

cache_controller = APIRouterPro(
    prefix='/monitor/cache', order_num=15, tags=['系统监控-缓存监控'], dependencies=[PreAuthDependency()]
)


@cache_controller.get(
    '',
    summary='获取缓存监控信息接口',
    description='用于获取缓存监控信息',
    response_model=DataResponseModel[CacheMonitorModel],
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
async def get_monitor_cache_info(request: Request) -> Response:
    result = await CacheService.get_cache_monitor_statistical_info_services(request.app.state.redis)
    logger.info('获取成功')
    return ResponseUtil.success(data=result)


@cache_controller.get(
    '/getNames',
    summary='获取缓存名称列表接口',
    description='用于获取缓存名称列表',
    response_model=DataResponseModel[list[CacheInfoModel]],
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
async def get_monitor_cache_name(request: Request) -> Response:
    result = await CacheService.get_cache_monitor_cache_name_services()
    logger.info('获取成功')
    return ResponseUtil.success(data=result)


@cache_controller.get(
    '/getKeys/{cache_name}',
    summary='获取缓存键列表接口',
    description='用于获取指定缓存名称下的所有缓存键列表',
    response_model=DataResponseModel[list[str]],
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
async def get_monitor_cache_key(request: Request, cache_name: Annotated[str, Path(description='缓存名称')]) -> Response:
    result = await CacheService.get_cache_monitor_cache_key_services(request.app.state.redis, cache_name)
    logger.info('获取成功')
    return ResponseUtil.success(data=result)


@cache_controller.get(
    '/getValue/{cache_name}/{cache_key}',
    summary='获取缓存值接口',
    description='用于获取指定缓存名称下的指定缓存键对应的值',
    response_model=DataResponseModel[CacheInfoModel],
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
async def get_monitor_cache_value(
    request: Request,
    cache_name: Annotated[str, Path(description='缓存名称')],
    cache_key: Annotated[str, Path(description='缓存键')],
) -> Response:
    result = await CacheService.get_cache_monitor_cache_value_services(request.app.state.redis, cache_name, cache_key)
    logger.info('获取成功')
    return ResponseUtil.success(data=result)


@cache_controller.delete(
    '/clearCacheName/{cache_name}',
    summary='清除缓存名称接口',
    description='用于清除指定缓存名称下的所有缓存键值对',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
@ApiRateLimit(namespace=ApiNamespace.MONITOR_CACHE_CLEAR_NAME, preset=ApiRateLimitPreset.USER_DESTRUCTIVE_MUTATION)
async def clear_monitor_cache_name(
    request: Request, cache_name: Annotated[str, Path(description='缓存名称')]
) -> Response:
    result = await CacheService.clear_cache_monitor_cache_name_services(request.app.state.redis, cache_name)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


@cache_controller.delete(
    '/clearCacheKey/{cache_key}',
    summary='清除缓存键接口',
    description='用于清除指定缓存键对应的值',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
@ApiRateLimit(namespace=ApiNamespace.MONITOR_CACHE_CLEAR_KEY, preset=ApiRateLimitPreset.USER_DESTRUCTIVE_MUTATION)
async def clear_monitor_cache_key(request: Request, cache_key: Annotated[str, Path(description='缓存键')]) -> Response:
    result = await CacheService.clear_cache_monitor_cache_key_services(request.app.state.redis, cache_key)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


@cache_controller.delete(
    '/clearCacheAll',
    summary='清除所有缓存接口',
    description='用于清除所有缓存键值对',
    response_model=ResponseBaseModel,
    dependencies=[UserInterfaceAuthDependency('monitor:cache:list')],
)
@ApiRateLimit(namespace=ApiNamespace.MONITOR_CACHE_CLEAR_ALL, preset=ApiRateLimitPreset.USER_DESTRUCTIVE_MUTATION)
async def clear_monitor_cache_all(request: Request) -> Response:
    result = await CacheService.clear_cache_monitor_all_services(request.app.state.redis)
    logger.info(result.message)
    return ResponseUtil.success(msg=result.message)


__all__ = ['cache_controller']
