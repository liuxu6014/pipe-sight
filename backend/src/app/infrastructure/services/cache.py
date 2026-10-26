"""Redis 缓存监控服务。"""

from redis import asyncio as aioredis

from app.infrastructure.schemas.cache import CacheInfoModel, CacheMonitorModel
from common.enums.cache import RedisInitKeyConfig
from common.http.schemas import CrudResponseModel
from config.get_redis import RedisUtil


class CacheService:
    """提供 Redis 运行信息和缓存键值运维操作。"""

    @classmethod
    async def get_cache_monitor_statistical_info_services(cls, redis: aioredis.Redis) -> CacheMonitorModel:
        info = await redis.info()
        db_size = await redis.dbsize()
        command_stats_dict = await redis.info('commandstats')
        command_stats = [
            {'name': key.split('_')[1], 'value': str(value.get('calls'))} for key, value in command_stats_dict.items()
        ]
        return CacheMonitorModel(commandStats=command_stats, dbSize=db_size, info=info)

    @classmethod
    async def get_cache_monitor_cache_name_services(cls) -> list[CacheInfoModel]:
        return [
            CacheInfoModel(cacheKey='', cacheName=key_config.key, cacheValue='', remark=key_config.remark)
            for key_config in RedisInitKeyConfig
        ]

    @classmethod
    async def get_cache_monitor_cache_key_services(cls, redis: aioredis.Redis, cache_name: str) -> list[str]:
        cache_keys: list[str] = await redis.keys(f'{cache_name}*')
        return [key.split(':', 1)[1] for key in cache_keys if key.startswith(f'{cache_name}:')]

    @classmethod
    async def get_cache_monitor_cache_value_services(
        cls, redis: aioredis.Redis, cache_name: str, cache_key: str
    ) -> CacheInfoModel:
        cache_value = await redis.get(f'{cache_name}:{cache_key}')
        return CacheInfoModel(cacheKey=cache_key, cacheName=cache_name, cacheValue=cache_value, remark='')

    @classmethod
    async def clear_cache_monitor_cache_name_services(cls, redis: aioredis.Redis, cache_name: str) -> CrudResponseModel:
        cache_keys = await redis.keys(f'{cache_name}*')
        if cache_keys:
            await redis.delete(*cache_keys)
        return CrudResponseModel(is_success=True, message=f'{cache_name}对应键值清除成功')

    @classmethod
    async def clear_cache_monitor_cache_key_services(cls, redis: aioredis.Redis, cache_key: str) -> CrudResponseModel:
        cache_keys = await redis.keys(f'*{cache_key}')
        if cache_keys:
            await redis.delete(*cache_keys)
        return CrudResponseModel(is_success=True, message=f'{cache_key}清除成功')

    @classmethod
    async def clear_cache_monitor_all_services(cls, redis: aioredis.Redis) -> CrudResponseModel:
        cache_keys = await redis.keys()
        if cache_keys:
            await redis.delete(*cache_keys)
        await RedisUtil.init_sys_dict(redis)
        await RedisUtil.init_sys_config(redis)
        return CrudResponseModel(is_success=True, message='所有缓存清除成功')


__all__ = ['CacheService']
