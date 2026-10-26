"""在线会话监控服务。

在线用户本质上是 Redis 中的认证会话视图，不属于用户、角色等身份主数据，
因此放在基础设施层并通过认证能力读取会话信息。
"""

from typing import Any

import jwt
from redis import asyncio as aioredis

from app.infrastructure.schemas.online import DeleteOnlineModel, OnlineQueryModel
from app.infrastructure.services.serialization import CamelCaseUtil
from common.enums.cache import RedisInitKeyConfig
from common.http.schemas import CrudResponseModel
from config.env import AppConfig, JwtConfig
from exceptions.exception import ServiceException


class OnlineService:
    """在线会话查询和强制下线服务。"""

    @classmethod
    async def get_online_list_services(
        cls, redis: aioredis.Redis, query_object: OnlineQueryModel
    ) -> list[dict[str, Any]]:
        """从 Redis 认证会话中构造在线用户列表。"""
        access_token_keys = await redis.keys(f'{RedisInitKeyConfig.ACCESS_TOKEN.key}*')
        if not access_token_keys:
            access_token_keys = []
        access_token_values_list = [await redis.get(key) for key in access_token_keys]
        online_info_list = []
        for item in access_token_values_list:
            payload = jwt.decode(item, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
            online_dict = {
                'token_id': payload.get('session_id') if AppConfig.app_same_time_login else payload.get('user_id'),
                'user_name': payload.get('user_name'),
                'ipaddr': payload.get('login_info').get('ipaddr'),
                'login_location': payload.get('login_info').get('loginLocation'),
                'browser': payload.get('login_info').get('browser'),
                'os': payload.get('login_info').get('os'),
                'login_time': payload.get('login_info').get('loginTime'),
            }
            if query_object.user_name and not query_object.ipaddr:
                if query_object.user_name == payload.get('user_name'):
                    online_info_list = [online_dict]
                    break
            elif not query_object.user_name and query_object.ipaddr:
                if query_object.ipaddr == payload.get('login_info').get('ipaddr'):
                    online_info_list = [online_dict]
                    break
            elif query_object.user_name and query_object.ipaddr:
                if query_object.user_name == payload.get('user_name') and query_object.ipaddr == payload.get(
                    'login_info'
                ).get('ipaddr'):
                    online_info_list = [online_dict]
                    break
            else:
                online_info_list.append(online_dict)

        return CamelCaseUtil.transform_result(online_info_list)

    @classmethod
    async def delete_online_services(cls, redis: aioredis.Redis, page_object: DeleteOnlineModel) -> CrudResponseModel:
        """删除 Redis 认证会话，使指定用户强制下线。"""
        if page_object.token_ids:
            token_id_list = page_object.token_ids.split(',')
            for token_id in token_id_list:
                await redis.delete(f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{token_id}')
            return CrudResponseModel(is_success=True, message='强退成功')
        raise ServiceException(message='传入session_id为空')


__all__ = ['OnlineService']
