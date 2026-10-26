"""应用组装入口。

API、Worker 和 CLI 共用此应用工厂。旧的 `server.py` 仅保留兼容导入，
不再拥有独立的应用组装实现。
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.entrypoints.routes import register_application_routers
from app.infrastructure.models.registry import register_sqlalchemy_models
from app.infrastructure.services.log import LogAggregatorService
from app.infrastructure.services.logging_support import logger
from app.infrastructure.services.runtime import APIDocsUtil, IPUtil, StartupUtil
from app.infrastructure.services.startup_banner import log_startup_banner
from app.infrastructure.services.transport_crypto_core import TransportKeyProvider
from app.intelligence.services.templates import PipelineTemplateService
from app.research.tasks.research_job_scheduler import stop_recovery_tasks
from common.constants import LockConstant
from config.database import AsyncSessionLocal
from config.env import AppConfig
from config.get_db import close_async_engine, init_create_table
from config.get_redis import RedisUtil
from config.get_scheduler import SchedulerUtil
from exceptions.handle import handle_exception
from middlewares.handle import handle_middleware
from sub_applications.handle import handle_sub_applications


async def _start_background_tasks(app: FastAPI) -> None:
    """
    启动应用后台任务

    :param app: FastAPI对象
    :return: None
    """
    await SchedulerUtil.init_system_scheduler(app.state.redis)
    app.state.log_aggregator_task = asyncio.create_task(LogAggregatorService.consume_stream(app.state.redis))


async def _stop_background_tasks(app: FastAPI) -> None:
    """
    停止应用后台任务并释放资源

    :param app: FastAPI对象
    :return: None
    """
    log_task = getattr(app.state, 'log_aggregator_task', None)
    if log_task:
        log_task.cancel()
        try:
            await log_task
        except asyncio.CancelledError:
            pass
    lock_task = getattr(app.state, 'lock_renewal_task', None)
    if lock_task:
        lock_task.cancel()
        try:
            await lock_task
        except asyncio.CancelledError:
            pass
    await RedisUtil.close_redis_pool(app)
    await stop_recovery_tasks()
    await SchedulerUtil.close_system_scheduler()
    await close_async_engine()


# 生命周期事件
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    :param app: FastAPI对象
    :return: None
    """
    app.state.redis = await RedisUtil.create_redis_pool(log_enabled=False)
    startup_log_enabled = await StartupUtil.acquire_startup_log_gate(
        redis=app.state.redis,
        lock_key=LockConstant.APP_STARTUP_LOCK_KEY,
        worker_id=SchedulerUtil._worker_id,
        lock_expire_seconds=LockConstant.LOCK_EXPIRE_SECONDS,
    )
    app.state.startup_log_enabled = startup_log_enabled

    # 获取锁成功后立即启动锁续期任务，避免初始化时间过长导致锁过期
    if startup_log_enabled:
        app.state.lock_renewal_task = StartupUtil.start_lock_renewal(
            redis=app.state.redis,
            lock_key=LockConstant.APP_STARTUP_LOCK_KEY,
            worker_id=SchedulerUtil._worker_id,
            lock_expire_seconds=LockConstant.LOCK_EXPIRE_SECONDS,
            interval_seconds=LockConstant.LOCK_RENEWAL_INTERVAL,
            on_lock_lost=SchedulerUtil.on_lock_lost,
        )

    with logger.contextualize(startup_phase=True, startup_log_enabled=startup_log_enabled):
        logger.info(f'⏰️ {AppConfig.app_name}开始启动')
        if startup_log_enabled:
            log_startup_banner()
        TransportKeyProvider.validate_runtime_configuration()
        await init_create_table()
        async with AsyncSessionLocal() as db:
            await PipelineTemplateService.ensure_default_templates(db)
            await db.commit()
        await RedisUtil.check_redis_connection(app.state.redis, log_enabled=startup_log_enabled)
        await RedisUtil.init_sys_dict(app.state.redis)
        await RedisUtil.init_sys_config(app.state.redis)
        await _start_background_tasks(app)

    if startup_log_enabled:
        # 短暂等待确保下面的启动日志在最后打印
        await asyncio.sleep(0.5)
        logger.info(f'🚀 {AppConfig.app_name}启动成功')
        host = AppConfig.app_host
        port = AppConfig.app_port
        if host == '0.0.0.0':
            local_ip = IPUtil.get_local_ip()
            network_ips = IPUtil.get_network_ips()
        else:
            local_ip = host
            network_ips = [host]

        app_links = [f'🏠 Local:    <cyan>http://{local_ip}:{port}</cyan>']
        app_links.extend(f'📡 Network:  <cyan>http://{ip}:{port}</cyan>' for ip in network_ips)
        logger.opt(colors=True).info('💻 应用地址:\n' + '\n'.join(app_links))

        if not AppConfig.app_disable_swagger:
            swagger_links = [f'🏠 Local:    <cyan>http://{local_ip}:{port}{APIDocsUtil.docs_url()}</cyan>']
            swagger_links.extend(
                f'📡 Network:  <cyan>http://{ip}:{port}{APIDocsUtil.docs_url()}</cyan>' for ip in network_ips
            )
            logger.opt(colors=True).info('📄 Swagger文档:\n' + '\n'.join(swagger_links))

        if not AppConfig.app_disable_redoc:
            redoc_links = [f'🏠 Local:    <cyan>http://{local_ip}:{port}{APIDocsUtil.redoc_url()}</cyan>']
            redoc_links.extend(
                f'📡 Network:  <cyan>http://{ip}:{port}{APIDocsUtil.redoc_url()}</cyan>' for ip in network_ips
            )
            logger.opt(colors=True).info('📚 ReDoc文档:\n' + '\n'.join(redoc_links))
    yield
    shutdown_log_enabled = getattr(app.state, 'startup_log_enabled', False)
    with logger.contextualize(startup_phase=True, startup_log_enabled=shutdown_log_enabled):
        await _stop_background_tasks(app)


def create_app() -> FastAPI:
    """
    创建FastAPI应用

    :return: FastAPI对象
    """
    # API 进程不会经过 Alembic 的模型发现流程。先显式注册全部持久化模型，
    # 确保跨领域外键在真实请求提交时可解析。
    register_sqlalchemy_models()
    # 配置API文档静态资源
    APIDocsUtil.setup_docs_static_resources()
    # 初始化FastAPI对象
    app = FastAPI(
        title=AppConfig.app_name,
        description=f'{AppConfig.app_name}接口文档',
        version=AppConfig.app_version,
        lifespan=lifespan,
        openapi_url=APIDocsUtil.proxy_openapi_url(),
        docs_url=APIDocsUtil.proxy_docs_url(),
        redoc_url=APIDocsUtil.proxy_redoc_url(),
        swagger_ui_oauth2_redirect_url=APIDocsUtil.proxy_oauth2_redirect_url(),
    )

    # 自定义API文档路由，修复无法直接通过后端地址访问文档的问题
    APIDocsUtil.custom_api_docs_router(app)

    # 挂载子应用
    handle_sub_applications(app)
    # 加载中间件处理方法
    handle_middleware(app)
    # 加载全局异常处理方法
    handle_exception(app)
    # 按入口清单显式注册路由，避免依赖目录通配扫描
    register_application_routers(app)

    return app
