"""Authentication service owned by the system bounded context."""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError
from redis import asyncio as aioredis
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.services.logging_support import logger
from app.infrastructure.services.serialization import CamelCaseUtil
from app.system.constants import MenuConstant
from app.system.models.menu import SysMenu
from app.system.models.user import SysUser
from app.system.repositories.authentication import login_by_account
from app.system.repositories.roles import RoleDao
from app.system.repositories.users import UserDao
from app.system.schemas.auth import MenuTreeModel, MetaModel, RouterModel, SmsCode, UserLogin, UserRegister
from app.system.schemas.role import RoleModel
from app.system.schemas.user import AddUserModel, CurrentUserModel, ResetUserModel, TokenData, UserInfoModel
from app.system.services.notification import SmsCodeNotifier
from app.system.services.passwords import PasswordService
from app.system.services.users import UserService
from common.constants import CommonConstant
from common.enums.cache import RedisInitKeyConfig
from common.http.schemas import CrudResponseModel
from config.env import AppConfig, JwtConfig
from exceptions.exception import AuthException, LoginException, ServiceException


class LoginService:
    """
    登录模块服务层
    """

    @classmethod
    async def authenticate_user(
        cls,
        redis: aioredis.Redis,
        query_db: AsyncSession,
        login_user: UserLogin,
        *,
        client_ip: str,
        referer: str | None = None,
    ) -> Row[tuple[SysUser]]:
        """
        根据用户名密码校验用户登录

        :param redis: redis对象
        :param query_db: orm对象
        :param login_user: 登录用户对象
        :param client_ip: 客户端IP
        :param referer: 请求来源页面
        :return: 校验结果
        """
        await cls.__check_login_ip(redis, client_ip)
        account_lock = await redis.get(f'{RedisInitKeyConfig.ACCOUNT_LOCK.key}:{login_user.user_name}')
        if login_user.user_name == account_lock:
            logger.warning('账号已锁定，请稍后再试')
            raise LoginException(data='', message='账号已锁定，请稍后再试')
        # 判断请求是否来自于api文档，如果是返回指定格式的结果，用于修复api文档认证成功后token显示undefined的bug
        request_from_swagger = referer.endswith('docs') if referer else False
        request_from_redoc = referer.endswith('redoc') if referer else False
        # 判断是否开启验证码，开启则验证，否则不验证（dev模式下来自API文档的登录请求不检验）
        if not login_user.captcha_enabled or (
            (request_from_swagger or request_from_redoc) and AppConfig.app_env == 'dev'
        ):
            pass
        else:
            await cls.__check_login_captcha(redis, login_user)
        user = await login_by_account(query_db, login_user.user_name)
        if not user:
            logger.warning('用户不存在')
            raise LoginException(data='', message='用户不存在')
        if not PasswordService.verify_password(login_user.password, user[0].password_hash):
            cache_password_error_count = await redis.get(
                f'{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.key}:{login_user.user_name}'
            )
            password_error_counted = 0
            if cache_password_error_count:
                password_error_counted = cache_password_error_count
            password_error_count = int(password_error_counted) + 1
            await redis.set(
                f'{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.key}:{login_user.user_name}',
                password_error_count,
                ex=timedelta(minutes=10),
            )
            if password_error_count > CommonConstant.PASSWORD_ERROR_COUNT:
                await redis.delete(f'{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.key}:{login_user.user_name}')
                await redis.set(
                    f'{RedisInitKeyConfig.ACCOUNT_LOCK.key}:{login_user.user_name}',
                    login_user.user_name,
                    ex=timedelta(minutes=10),
                )
                logger.warning('10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试')
                raise LoginException(data='', message='10分钟内密码已输错超过5次，账号已锁定，请10分钟后再试')
            logger.warning('密码错误')
            raise LoginException(data='', message='密码错误')
        if user[0].status == '1':
            logger.warning('用户已停用')
            raise LoginException(data='', message='用户已停用')
        await redis.delete(f'{RedisInitKeyConfig.PASSWORD_ERROR_COUNT.key}:{login_user.user_name}')
        return user

    @classmethod
    async def __check_login_ip(cls, redis: aioredis.Redis, client_ip: str) -> bool:
        """
        校验用户登录ip是否在黑名单内

        :param redis: redis对象
        :param client_ip: 客户端IP
        :return: 校验结果
        """
        black_ip_value = await redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.login.blackIPList')
        black_ip_list = black_ip_value.split(',') if black_ip_value else []
        if client_ip in black_ip_list:
            logger.warning('当前IP禁止登录')
            raise LoginException(data='', message='当前IP禁止登录')
        return True

    @classmethod
    async def __check_login_captcha(cls, redis: aioredis.Redis, login_user: UserLogin) -> bool:
        """
        校验用户登录验证码

        :param redis: redis对象
        :param login_user: 登录用户对象
        :return: 校验结果
        """
        captcha_value = await redis.get(f'{RedisInitKeyConfig.CAPTCHA_CODES.key}:{login_user.uuid}')
        if not captcha_value:
            logger.warning('验证码已失效')
            raise LoginException(data='', message='验证码已失效')
        if login_user.code != str(captcha_value):
            logger.warning('验证码错误')
            raise LoginException(data='', message='验证码错误')
        return True

    @classmethod
    async def create_access_token(cls, data: dict, expires_delta: timedelta | None = None) -> str:
        """
        根据登录信息创建当前用户token

        :param data: 登录信息
        :param expires_delta: token有效期
        :return: token
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        to_encode.update({'exp': expire})
        encoded_jwt = jwt.encode(to_encode, JwtConfig.jwt_secret_key, algorithm=JwtConfig.jwt_algorithm)
        return encoded_jwt

    @classmethod
    async def get_current_user(cls, redis: aioredis.Redis, token: str, query_db: AsyncSession) -> CurrentUserModel:
        """
        根据token获取当前用户信息

        :param redis: redis对象
        :param token: 用户token
        :param query_db: orm对象
        :return: 当前用户信息对象
        :raise: 令牌异常AuthException
        """
        # if token[:6] != 'Bearer':
        #     logger.warning("用户token不合法")
        #     raise AuthException(data="", message="用户token不合法")
        try:
            if token.startswith('Bearer'):
                token = token.split(' ')[1]
            payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
            user_id: str = payload.get('user_id')
            session_id: str = payload.get('session_id')
            if not user_id:
                logger.warning('用户token不合法')
                raise AuthException(data='', message='用户token不合法')
            token_data = TokenData(user_id=int(user_id))
        except InvalidTokenError as e:
            logger.warning('用户token已失效，请重新登录')
            raise AuthException(data='', message='用户token已失效，请重新登录') from e
        query_user = await UserDao.get_user_by_id(query_db, user_id=token_data.user_id)
        if query_user.get('user_basic_info') is None:
            logger.warning('用户token不合法')
            raise AuthException(data='', message='用户token不合法')
        if AppConfig.app_same_time_login:
            redis_token = await redis.get(f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}')
        else:
            # 此方法可实现同一账号同一时间只能登录一次
            redis_token = await redis.get(
                f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{query_user.get("user_basic_info").id}'
            )
        if token == redis_token:
            if AppConfig.app_same_time_login:
                await redis.set(
                    f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}',
                    redis_token,
                    ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
                )
            else:
                await redis.set(
                    f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{query_user.get("user_basic_info").id}',
                    redis_token,
                    ex=timedelta(minutes=JwtConfig.jwt_redis_expire_minutes),
                )

            role_id_list = [item.id for item in query_user.get('user_role_info')]
            if 1 in role_id_list:
                permissions = ['*:*:*']
            else:
                permissions = [row.permissions for row in query_user.get('user_menu_info')]
            role_ids = ','.join([str(row.id) for row in query_user.get('user_role_info')])
            roles = [row.code for row in query_user.get('user_role_info')]
            is_default_modify_pwd = await cls.__init_password_is_modify(
                redis, query_user.get('user_basic_info').password_updated_at
            )
            is_password_expired = await cls.__password_is_expired(
                redis, query_user.get('user_basic_info').password_updated_at
            )

            current_user = CurrentUserModel(
                permissions=permissions,
                roles=roles,
                user=UserInfoModel(
                    **CamelCaseUtil.transform_result(query_user.get('user_basic_info')),
                    roleIds=role_ids,
                    role=CamelCaseUtil.transform_result(query_user.get('user_role_info')),
                ),
                isDefaultModifyPwd=is_default_modify_pwd,
                isPasswordExpired=is_password_expired,
            )
            return current_user
        logger.warning('用户token已失效，请重新登录')
        raise AuthException(data='', message='用户token已失效，请重新登录')

    @classmethod
    async def __init_password_is_modify(cls, redis: aioredis.Redis, pwd_update_date: datetime) -> bool:
        """
        判断当前用户是否初始密码登录

        :param redis: redis对象
        :param pwd_update_date: 密码最后更新时间
        :return: 是否初始密码登录
        """
        init_password_is_modify = await redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.initPasswordModify')
        return init_password_is_modify == '1' and pwd_update_date is None

    @classmethod
    async def __password_is_expired(cls, redis: aioredis.Redis, pwd_update_date: datetime) -> bool:
        """
        判断当前用户密码是否过期

        :param redis: redis对象
        :param pwd_update_date: 密码最后更新时间
        :return: 密码是否过期
        """
        password_validate_days = await redis.get(
            f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.passwordValidateDays'
        )
        if password_validate_days and int(password_validate_days) > 0:
            if pwd_update_date is None:
                return True
            expire_date = pwd_update_date + timedelta(days=int(password_validate_days))
            if datetime.now() > expire_date:
                return True
        return False

    @classmethod
    async def get_current_user_routers(cls, user_id: int, query_db: AsyncSession) -> list[dict[str, Any]]:
        """
        根据用户id获取当前用户路由信息

        :param user_id: 用户id
        :param query_db: orm对象
        :return: 当前用户路由信息对象
        """
        query_user = await UserDao.get_user_by_id(query_db, user_id=user_id)
        user_router_menu = sorted(
            [
                row
                for row in query_user.get('user_menu_info')
                if row.type in [MenuConstant.TYPE_DIR, MenuConstant.TYPE_MENU]
            ],
            key=lambda x: x.sort_order,
        )
        menus = cls.__generate_menus(0, user_router_menu)
        user_router = cls.__generate_user_router_menu(menus)
        return [router.model_dump(exclude_unset=True, by_alias=True) for router in user_router]

    @classmethod
    def __generate_menus(cls, pid: int, permission_list: list[SysMenu]) -> list[MenuTreeModel]:
        """
        工具方法：根据菜单信息生成菜单信息树形嵌套数据

        :param pid: 菜单id
        :param permission_list: 菜单列表信息
        :return: 菜单信息树形嵌套数据
        """
        menu_list: list[MenuTreeModel] = []
        for permission in permission_list:
            if permission.parent_id == pid:
                children = cls.__generate_menus(permission.id, permission_list)
                menu_list_data = MenuTreeModel(**CamelCaseUtil.transform_result(permission))
                if children:
                    menu_list_data.children = children
                menu_list.append(menu_list_data)

        return menu_list

    @classmethod
    def __generate_user_router_menu(cls, permission_list: list[MenuTreeModel]) -> list[RouterModel]:
        """
        工具方法：根据菜单树信息生成路由信息树形嵌套数据

        :param permission_list: 菜单树列表信息
        :return: 路由信息树形嵌套数据
        """
        router_list: list[RouterModel] = []
        for permission in permission_list:
            router = RouterModel(
                hidden=permission.visible == '1',
                name=RouterUtil.get_router_name(permission),
                path=RouterUtil.get_router_path(permission),
                component=RouterUtil.get_component(permission),
                query=permission.query,
                meta=MetaModel(
                    title=permission.menu_name,
                    icon=permission.icon,
                    noCache=permission.is_cache == 1,
                    link=permission.path if RouterUtil.is_http(permission.path) else None,
                ),
            )
            c_menus = permission.children
            if c_menus and permission.menu_type == MenuConstant.TYPE_DIR:
                router.always_show = True
                router.redirect = 'noRedirect'
                router.children = cls.__generate_user_router_menu(c_menus)
            elif RouterUtil.is_menu_frame(permission):
                router.meta = None
                children_list: list[RouterModel] = []
                children = RouterModel(
                    path=permission.path,
                    component=permission.component,
                    name=RouterUtil.get_route_name(permission.route_name, permission.path),
                    meta=MetaModel(
                        title=permission.menu_name,
                        icon=permission.icon,
                        noCache=permission.is_cache == 1,
                        link=permission.path if RouterUtil.is_http(permission.path) else None,
                    ),
                    query=permission.query,
                )
                children_list.append(children)
                router.children = children_list
            elif permission.parent_id == 0 and RouterUtil.is_inner_link(permission):
                router.meta = MetaModel(title=permission.menu_name, icon=permission.icon)
                router.path = '/'
                children_list: list[RouterModel] = []
                router_path = RouterUtil.inner_link_replace_each(permission.path)
                children = RouterModel(
                    path=router_path,
                    component=MenuConstant.INNER_LINK,
                    name=RouterUtil.get_route_name(permission.route_name, permission.path),
                    meta=MetaModel(
                        title=permission.menu_name,
                        icon=permission.icon,
                        link=permission.path if RouterUtil.is_http(permission.path) else None,
                    ),
                )
                children_list.append(children)
                router.children = children_list

            router_list.append(router)

        return router_list

    @classmethod
    async def register_user_services(
        cls, redis: aioredis.Redis, query_db: AsyncSession, user_register: UserRegister
    ) -> CrudResponseModel:
        """
        用户注册services

        :param redis: redis对象
        :param query_db: orm对象
        :param user_register: 注册用户对象
        :return: 注册结果
        """
        register_enabled = await redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.registerUser') == 'true'
        captcha_enabled = await redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.captchaEnabled') == 'true'
        if user_register.password == user_register.confirm_password:
            if register_enabled:
                if captcha_enabled:
                    captcha_value = await redis.get(f'{RedisInitKeyConfig.CAPTCHA_CODES.key}:{user_register.uuid}')
                    if not captcha_value:
                        raise ServiceException(message='验证码已失效')
                    if user_register.code != str(captcha_value):
                        raise ServiceException(message='验证码错误')
                common_role = await RoleDao.get_role_by_info(query_db, RoleModel(roleKey='common'))
                if common_role is None:
                    raise ServiceException(message='普通用户角色未初始化，暂时无法注册')
                add_user = AddUserModel(
                    userName=user_register.username,
                    nickName=user_register.username,
                    password=PasswordService.get_password_hash(user_register.password),
                    pwdUpdateDate=datetime.now(),
                    roleIds=[common_role.id],
                )
                result = await UserService.add_user_services(query_db, add_user)
                return result
            raise ServiceException(message='注册程序已关闭，禁止注册')
        raise ServiceException(message='两次输入的密码不一致')

    @classmethod
    async def get_sms_code_services(
        cls, redis: aioredis.Redis, query_db: AsyncSession, user: ResetUserModel
    ) -> SmsCode:
        """
        获取短信验证码service

        :param redis: redis对象
        :param query_db: orm对象
        :param user: 用户对象
        :return: 短信验证码对象
        """
        redis_sms_result = await redis.get(f'{RedisInitKeyConfig.SMS_CODE.key}:{user.session_id}')
        if redis_sms_result:
            return SmsCode(is_success=False, sms_code='', session_id='', message='短信验证码仍在有效期内')
        is_user = await UserDao.get_user_by_name(query_db, user.user_name)
        if is_user:
            sms_code = str(random.randint(100000, 999999))
            session_id = str(uuid.uuid4())
            await redis.set(f'{RedisInitKeyConfig.SMS_CODE.key}:{session_id}', sms_code, ex=timedelta(minutes=2))
            # 此处模拟调用短信服务
            SmsCodeNotifier.notify(sms_code)

            return SmsCode(is_success=True, sms_code=sms_code, session_id=session_id, message='获取成功')

        return SmsCode(is_success=False, sms_code='', session_id='', message='用户不存在')

    @classmethod
    async def forget_user_services(
        cls, redis: aioredis.Redis, query_db: AsyncSession, forget_user: ResetUserModel
    ) -> CrudResponseModel:
        """
        用户忘记密码services

        :param redis: redis对象
        :param query_db: orm对象
        :param forget_user: 重置用户对象
        :return: 重置结果
        """
        redis_sms_result = await redis.get(f'{RedisInitKeyConfig.SMS_CODE.key}:{forget_user.session_id}')
        if forget_user.sms_code == redis_sms_result:
            forget_user.password = PasswordService.get_password_hash(forget_user.password)
            forget_user.user_id = (await UserDao.get_user_by_name(query_db, forget_user.user_name)).id
            edit_result = await UserService.reset_user_services(query_db, forget_user)
            result = edit_result.dict()
        elif not redis_sms_result:
            result = {'is_success': False, 'message': '短信验证码已过期'}
        else:
            await redis.delete(f'{RedisInitKeyConfig.SMS_CODE.key}:{forget_user.session_id}')
            result = {'is_success': False, 'message': '短信验证码不正确'}

        return CrudResponseModel(**result)

    @classmethod
    async def logout_services(cls, redis: aioredis.Redis, token_id: str) -> bool:
        """
        退出登录services

        :param redis: redis对象
        :param token_id: 令牌编号
        :return: 退出登录结果
        """
        await redis.delete(f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{token_id}')

        return True


class RouterUtil:
    """
    路由处理工具类
    """

    @classmethod
    def get_router_name(cls, menu: MenuTreeModel) -> str:
        """
        获取路由名称

        :param menu: 菜单数对象
        :return: 路由名称
        """
        # 非外链并且是一级目录（类型为目录）
        if cls.is_menu_frame(menu):
            return ''

        return cls.get_route_name(menu.route_name, menu.path)

    @classmethod
    def get_route_name(cls, name: str, path: str) -> str:
        """
        获取路由名称，如没有配置路由名称则取路由地址

        :param name: 路由名称
        :param path: 路由地址
        :return: 路由名称（驼峰格式）
        """
        router_name = name if name else path
        return router_name.capitalize()

    @classmethod
    def get_router_path(cls, menu: MenuTreeModel) -> str | None:
        """
        获取路由地址

        :param menu: 菜单数对象
        :return: 路由地址
        """
        # 内链打开外网方式
        router_path = menu.path
        if menu.parent_id != 0 and cls.is_inner_link(menu):
            router_path = cls.inner_link_replace_each(router_path)
        # 非外链并且是一级目录（类型为目录）
        if menu.parent_id == 0 and menu.menu_type == MenuConstant.TYPE_DIR and menu.is_frame == MenuConstant.NO_FRAME:
            router_path = f'/{menu.path}'
        # 非外链并且是一级目录（类型为菜单）
        elif cls.is_menu_frame(menu):
            router_path = '/'
        return router_path

    @classmethod
    def get_component(cls, menu: MenuTreeModel) -> str:
        """
        获取组件信息

        :param menu: 菜单数对象
        :return: 组件信息
        """
        component = MenuConstant.LAYOUT
        if menu.component and not cls.is_menu_frame(menu):
            component = menu.component
        elif (menu.component is None or menu.component == '') and menu.parent_id != 0 and cls.is_inner_link(menu):
            component = MenuConstant.INNER_LINK
        elif (menu.component is None or menu.component == '') and cls.is_parent_view(menu):
            component = MenuConstant.PARENT_VIEW
        return component

    @classmethod
    def is_menu_frame(cls, menu: MenuTreeModel) -> bool:
        """
        判断是否为菜单内部跳转

        :param menu: 菜单数对象
        :return: 是否为菜单内部跳转
        """
        return (
            menu.parent_id == 0 and menu.menu_type == MenuConstant.TYPE_MENU and menu.is_frame == MenuConstant.NO_FRAME
        )

    @classmethod
    def is_inner_link(cls, menu: MenuTreeModel) -> bool:
        """
        判断是否为内链组件

        :param menu: 菜单数对象
        :return: 是否为内链组件
        """
        return menu.is_frame == MenuConstant.NO_FRAME and cls.is_http(menu.path)

    @classmethod
    def is_parent_view(cls, menu: MenuTreeModel) -> bool:
        """
        判断是否为parent_view组件

        :param menu: 菜单数对象
        :return: 是否为parent_view组件
        """
        return menu.parent_id != 0 and menu.menu_type == MenuConstant.TYPE_DIR

    @classmethod
    def is_http(cls, link: str) -> bool:
        """
        判断是否为http(s)://开头

        :param link: 链接
        :return: 是否为http(s)://开头
        """
        return link.startswith((CommonConstant.HTTP, CommonConstant.HTTPS))

    @classmethod
    def inner_link_replace_each(cls, path: str) -> str:
        """
        内链域名特殊字符替换

        :param path: 内链域名
        :return: 替换后的内链域名
        """
        old_values = [CommonConstant.HTTP, CommonConstant.HTTPS, CommonConstant.WWW, '.', ':']
        new_values = ['', '', '', '/', '/']
        for old, new in zip(old_values, new_values, strict=False):
            path = path.replace(old, new)
        return path
