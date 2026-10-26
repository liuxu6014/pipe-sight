"""HTTP 接口命名空间及缓存失效分组契约。"""

class ApiNamespace:
    """
    接口注解通用命名空间常量

    这一组常量统一提供给 `ApiCache`、`ApiCacheEvict`、`ApiRateLimit`
    等接口注解使用，用同一套“模块:功能”命名规则收敛缓存和限流场景。

    LOGIN: 登录接口命名空间
    REGISTER: 注册接口命名空间
    LOGIN_USER_INFO: 登录用户信息接口命名空间
    LOGIN_USER_ROUTERS: 登录用户路由接口命名空间
    CAPTCHA_IMAGE: 图片验证码接口命名空间
    COMMON_UPLOAD: 通用上传接口命名空间
    TRANSPORT_CRYPTO_PUBLIC_KEY: 传输层加密公钥接口命名空间
    TRANSPORT_CRYPTO_FRONTEND_CONFIG: 传输层加密前端配置接口命名空间

    MONITOR_SERVER_INFO: 服务监控信息接口命名空间
    MONITOR_CACHE_CLEAR_NAME: 缓存名称清理接口命名空间
    MONITOR_CACHE_CLEAR_KEY: 缓存键清理接口命名空间
    MONITOR_CACHE_CLEAR_ALL: 缓存全量清理接口命名空间
    MONITOR_ONLINE_FORCE_LOGOUT: 在线用户强退接口命名空间
    MONITOR_OPERLOG_CLEAN: 操作日志清空接口命名空间
    MONITOR_OPERLOG_DELETE: 操作日志删除接口命名空间
    MONITOR_OPERLOG_EXPORT: 操作日志导出接口命名空间
    MONITOR_LOGININFO_CLEAN: 登录日志清空接口命名空间
    MONITOR_LOGININFO_DELETE: 登录日志删除接口命名空间
    MONITOR_LOGININFO_UNLOCK: 账户解锁接口命名空间
    MONITOR_LOGININFO_EXPORT: 登录日志导出接口命名空间
    MONITOR_JOB_LIST: 定时任务分页列表接口命名空间
    MONITOR_JOB_DETAIL: 定时任务详情接口命名空间
    MONITOR_JOB_RUN: 定时任务执行接口命名空间
    MONITOR_JOB_DELETE: 定时任务删除接口命名空间
    MONITOR_JOB_EXPORT: 定时任务导出接口命名空间
    MONITOR_JOB_LOG_CLEAN: 定时任务日志清空接口命名空间
    MONITOR_JOB_LOG_DELETE: 定时任务日志删除接口命名空间
    MONITOR_JOB_LOG_EXPORT: 定时任务日志导出接口命名空间

    SYSTEM_CONFIG_LIST: 参数配置列表接口命名空间
    SYSTEM_CONFIG_DETAIL: 参数配置详情接口命名空间
    SYSTEM_CONFIG_REFRESH_CACHE: 参数缓存刷新接口命名空间
    SYSTEM_CONFIG_EXPORT: 参数导出接口命名空间
    SYSTEM_DICT_TYPE_LIST: 字典类型列表接口命名空间
    SYSTEM_DICT_TYPE_OPTIONS: 字典类型选项接口命名空间
    SYSTEM_DICT_TYPE_DETAIL: 字典类型详情接口命名空间
    SYSTEM_DICT_REFRESH_CACHE: 字典缓存刷新接口命名空间
    SYSTEM_DICT_TYPE_EXPORT: 字典类型导出接口命名空间
    SYSTEM_DICT_DATA_LIST: 字典数据列表接口命名空间
    SYSTEM_DICT_DATA_DETAIL: 字典数据详情接口命名空间
    SYSTEM_DICT_DATA_EXPORT: 字典数据导出接口命名空间
    SYSTEM_MENU_TREE: 菜单树接口命名空间
    SYSTEM_MENU_ROLE_TREE: 角色菜单树接口命名空间
    SYSTEM_MENU_LIST: 菜单分页列表接口命名空间
    SYSTEM_MENU_DETAIL: 菜单详情接口命名空间
    SYSTEM_ROLE_LIST: 角色列表接口命名空间
    SYSTEM_ROLE_DETAIL: 角色详情接口命名空间
    SYSTEM_ROLE_ALLOCATED_USER_LIST: 已分配用户角色列表接口命名空间
    SYSTEM_ROLE_UNALLOCATED_USER_LIST: 未分配用户角色列表接口命名空间
    SYSTEM_ROLE_EXPORT: 角色导出接口命名空间
    SYSTEM_ROLE_AUTH_USER_SELECT_ALL: 角色批量分配用户接口命名空间
    SYSTEM_ROLE_AUTH_USER_CANCEL: 角色取消分配用户接口命名空间
    SYSTEM_ROLE_AUTH_USER_CANCEL_ALL: 角色批量取消分配用户接口命名空间
    SYSTEM_USER_LIST: 用户列表接口命名空间
    SYSTEM_USER_PROFILE: 用户个人信息接口命名空间
    SYSTEM_USER_DETAIL: 用户详情接口命名空间
    SYSTEM_USER_PROFILE_AVATAR: 用户头像上传接口命名空间
    SYSTEM_USER_IMPORT: 用户导入接口命名空间
    SYSTEM_USER_EXPORT: 用户导出接口命名空间

    AI_MODEL_LIST: AI模型列表接口命名空间
    AI_MODEL_ALL: AI模型全量列表接口命名空间
    AI_MODEL_DETAIL: AI模型详情接口命名空间

    """

    LOGIN = 'login'
    REGISTER = 'register'
    LOGIN_USER_INFO = 'login:user:info'
    LOGIN_USER_ROUTERS = 'login:user:routers'
    CAPTCHA_IMAGE = 'captcha:image'
    COMMON_UPLOAD = 'common:upload'
    TRANSPORT_CRYPTO_PUBLIC_KEY = 'transport-crypto:public-key'
    TRANSPORT_CRYPTO_FRONTEND_CONFIG = 'transport-crypto:frontend-config'

    MONITOR_SERVER_INFO = 'monitor:server:info'
    MONITOR_CACHE_CLEAR_NAME = 'monitor:cache:clear-name'
    MONITOR_CACHE_CLEAR_KEY = 'monitor:cache:clear-key'
    MONITOR_CACHE_CLEAR_ALL = 'monitor:cache:clear-all'
    MONITOR_ONLINE_FORCE_LOGOUT = 'monitor:online:force-logout'
    MONITOR_OPERLOG_CLEAN = 'monitor:operlog:clean'
    MONITOR_OPERLOG_DELETE = 'monitor:operlog:delete'
    MONITOR_OPERLOG_EXPORT = 'monitor:operlog:export'
    MONITOR_LOGININFO_CLEAN = 'monitor:logininfor:clean'
    MONITOR_LOGININFO_DELETE = 'monitor:logininfor:delete'
    MONITOR_LOGININFO_UNLOCK = 'monitor:logininfor:unlock'
    MONITOR_LOGININFO_EXPORT = 'monitor:logininfor:export'
    MONITOR_JOB_LIST = 'monitor:job:list'
    MONITOR_JOB_DETAIL = 'monitor:job:detail'
    MONITOR_JOB_RUN = 'monitor:job:run'
    MONITOR_JOB_DELETE = 'monitor:job:delete'
    MONITOR_JOB_EXPORT = 'monitor:job:export'
    MONITOR_JOB_LOG_CLEAN = 'monitor:job-log:clean'
    MONITOR_JOB_LOG_DELETE = 'monitor:job-log:delete'
    MONITOR_JOB_LOG_EXPORT = 'monitor:job-log:export'

    SYSTEM_CONFIG_LIST = 'system:config:list'
    SYSTEM_CONFIG_DETAIL = 'system:config:detail'
    SYSTEM_CONFIG_REFRESH_CACHE = 'system:config:refresh-cache'
    SYSTEM_CONFIG_EXPORT = 'system:config:export'

    SYSTEM_DICT_TYPE_LIST = 'system:dict:type-list'
    SYSTEM_DICT_TYPE_OPTIONS = 'system:dict:type-options'
    SYSTEM_DICT_TYPE_DETAIL = 'system:dict:type-detail'
    SYSTEM_DICT_REFRESH_CACHE = 'system:dict:refresh-cache'
    SYSTEM_DICT_TYPE_EXPORT = 'system:dict:type-export'
    SYSTEM_DICT_DATA_LIST = 'system:dict:data-list'
    SYSTEM_DICT_DATA_DETAIL = 'system:dict:data-detail'
    SYSTEM_DICT_DATA_EXPORT = 'system:dict:data-export'

    SYSTEM_MENU_TREE = 'system:menu:tree'
    SYSTEM_MENU_ROLE_TREE = 'system:menu:role-tree'
    SYSTEM_MENU_LIST = 'system:menu:list'
    SYSTEM_MENU_DETAIL = 'system:menu:detail'

    SYSTEM_ROLE_LIST = 'system:role:list'
    SYSTEM_ROLE_DETAIL = 'system:role:detail'
    SYSTEM_ROLE_ALLOCATED_USER_LIST = 'system:role:allocated-user-list'
    SYSTEM_ROLE_UNALLOCATED_USER_LIST = 'system:role:unallocated-user-list'
    SYSTEM_ROLE_EXPORT = 'system:role:export'
    SYSTEM_ROLE_AUTH_USER_SELECT_ALL = 'system:role:auth-user-select-all'
    SYSTEM_ROLE_AUTH_USER_CANCEL = 'system:role:auth-user-cancel'
    SYSTEM_ROLE_AUTH_USER_CANCEL_ALL = 'system:role:auth-user-cancel-all'

    SYSTEM_USER_LIST = 'system:user:list'
    SYSTEM_USER_PROFILE = 'system:user:profile'
    SYSTEM_USER_DETAIL = 'system:user:detail'
    SYSTEM_USER_PROFILE_AVATAR = 'system:user:profile-avatar'
    SYSTEM_USER_IMPORT = 'system:user:import'
    SYSTEM_USER_EXPORT = 'system:user:export'

    AI_MODEL_LIST = 'ai:model:list'
    AI_MODEL_ALL = 'ai:model:all'
    AI_MODEL_DETAIL = 'ai:model:detail'

class ApiGroup:
    """
    接口命名空间分组常量

    当前主要用于 `ApiCacheEvict` 批量清理关联命名空间，分组成员均来自
    `ApiNamespace`，按业务写操作影响范围收敛管理。

    PERMISSION_MUTATION: 权限与菜单视图关联命名空间分组
    DATA_SCOPE_MUTATION: 数据范围相关视图关联命名空间分组
    MENU_MUTATION: 菜单写操作关联命名空间分组
    JOB_MUTATION: 定时任务写操作关联命名空间分组
    ROLE_ENTITY_MUTATION: 角色实体信息变更关联命名空间分组
    ROLE_PERMISSION_MUTATION: 角色权限变更关联命名空间分组
    ROLE_MUTATION: 角色通用写操作关联命名空间组合分组
    USER_ENTITY_MUTATION: 用户实体信息变更关联命名空间分组
    USER_PERMISSION_MUTATION: 用户权限变更关联命名空间分组
    USER_INFO_MUTATION: 用户资料与安全相关写操作关联命名空间分组
    LOGIN_SUCCESS_MUTATION: 登录成功后关联命名空间分组
    LOGOUT_MUTATION: 登出后关联命名空间分组
    CONFIG_MUTATION: 参数配置写操作关联命名空间分组
    DICT_TYPE_MUTATION: 字典类型写操作关联命名空间分组
    DICT_DATA_MUTATION: 字典数据写操作关联命名空间分组
    AI_MODEL_MUTATION: AI模型写操作关联命名空间分组
    """

    PERMISSION_MUTATION = (
        ApiNamespace.LOGIN_USER_INFO,
        ApiNamespace.LOGIN_USER_ROUTERS,
        ApiNamespace.SYSTEM_MENU_TREE,
        ApiNamespace.SYSTEM_MENU_ROLE_TREE,
        ApiNamespace.SYSTEM_MENU_LIST,
    )

    DATA_SCOPE_MUTATION = (
        ApiNamespace.LOGIN_USER_INFO,
        ApiNamespace.SYSTEM_ROLE_LIST,
        ApiNamespace.SYSTEM_ROLE_DETAIL,
        ApiNamespace.SYSTEM_ROLE_ALLOCATED_USER_LIST,
        ApiNamespace.SYSTEM_ROLE_UNALLOCATED_USER_LIST,
        ApiNamespace.SYSTEM_USER_LIST,
        ApiNamespace.SYSTEM_USER_DETAIL,
        ApiNamespace.SYSTEM_USER_PROFILE,
        ApiNamespace.AI_MODEL_LIST,
        ApiNamespace.AI_MODEL_ALL,
        ApiNamespace.AI_MODEL_DETAIL,
    )

    MENU_MUTATION = (
        *PERMISSION_MUTATION,
        ApiNamespace.SYSTEM_MENU_DETAIL,
    )

    JOB_MUTATION = (
        ApiNamespace.MONITOR_JOB_LIST,
        ApiNamespace.MONITOR_JOB_DETAIL,
    )

    ROLE_ENTITY_MUTATION = (
        ApiNamespace.SYSTEM_ROLE_LIST,
        ApiNamespace.SYSTEM_ROLE_DETAIL,
        ApiNamespace.SYSTEM_ROLE_ALLOCATED_USER_LIST,
        ApiNamespace.SYSTEM_ROLE_UNALLOCATED_USER_LIST,
        ApiNamespace.SYSTEM_MENU_ROLE_TREE,
        ApiNamespace.SYSTEM_USER_DETAIL,
    )

    ROLE_PERMISSION_MUTATION = (
        *ROLE_ENTITY_MUTATION,
        ApiNamespace.SYSTEM_USER_PROFILE,
        ApiNamespace.LOGIN_USER_INFO,
        *PERMISSION_MUTATION,
    )

    ROLE_MUTATION = (
        *ROLE_PERMISSION_MUTATION,
        *DATA_SCOPE_MUTATION,
    )

    USER_ENTITY_MUTATION = (
        ApiNamespace.SYSTEM_USER_LIST,
        ApiNamespace.SYSTEM_USER_DETAIL,
        ApiNamespace.SYSTEM_ROLE_ALLOCATED_USER_LIST,
        ApiNamespace.SYSTEM_ROLE_UNALLOCATED_USER_LIST,
    )

    USER_PERMISSION_MUTATION = (
        *DATA_SCOPE_MUTATION,
        *PERMISSION_MUTATION,
    )

    USER_INFO_MUTATION = (
        ApiNamespace.SYSTEM_USER_LIST,
        ApiNamespace.SYSTEM_USER_DETAIL,
        ApiNamespace.SYSTEM_USER_PROFILE,
        ApiNamespace.LOGIN_USER_INFO,
    )

    LOGIN_SUCCESS_MUTATION = (
        ApiNamespace.SYSTEM_USER_LIST,
        ApiNamespace.LOGIN_USER_INFO,
        ApiNamespace.LOGIN_USER_ROUTERS,
        ApiNamespace.SYSTEM_USER_PROFILE,
        ApiNamespace.SYSTEM_USER_DETAIL,
    )

    LOGOUT_MUTATION = (
        ApiNamespace.LOGIN_USER_INFO,
        ApiNamespace.LOGIN_USER_ROUTERS,
    )

    CONFIG_MUTATION = (
        ApiNamespace.SYSTEM_CONFIG_LIST,
        ApiNamespace.SYSTEM_CONFIG_DETAIL,
    )

    DICT_TYPE_MUTATION = (
        ApiNamespace.SYSTEM_DICT_TYPE_LIST,
        ApiNamespace.SYSTEM_DICT_TYPE_OPTIONS,
        ApiNamespace.SYSTEM_DICT_TYPE_DETAIL,
        ApiNamespace.SYSTEM_DICT_DATA_LIST,
        ApiNamespace.SYSTEM_DICT_DATA_DETAIL,
    )

    DICT_DATA_MUTATION = (
        ApiNamespace.SYSTEM_DICT_DATA_LIST,
        ApiNamespace.SYSTEM_DICT_DATA_DETAIL,
    )

    AI_MODEL_MUTATION = (
        ApiNamespace.AI_MODEL_LIST,
        ApiNamespace.AI_MODEL_ALL,
        ApiNamespace.AI_MODEL_DETAIL,
    )

