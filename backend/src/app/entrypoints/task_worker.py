"""PipeSight 持久任务 Worker 入口。

该进程负责数据源采集、生成任务、图片/报告资源和资料解析，不启动
FastAPI 或系统定时任务，避免 API 进程承担长任务调度和执行压力。
"""

from __future__ import annotations

import asyncio
import signal

from app.infrastructure.models.registry import register_sqlalchemy_models
from app.infrastructure.services.logging_support import logger
from app.intelligence.tasks.operational_scheduler import run_operational_scheduler
from app.research.tasks.research_job_scheduler import run_persistent_recovery_loop
from config.get_db import close_async_engine, init_create_table

# 独立进程同样只使用已迁移结构，不借助 API 导入顺序或自动建表修补依赖。


async def _run_worker() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)
    except (NotImplementedError, RuntimeError):
        # Windows 或非主线程事件循环不支持 Unix signal handler；取消任务仍可退出。
        pass

    try:
        register_sqlalchemy_models()
        await init_create_table()
        await asyncio.gather(
            run_persistent_recovery_loop(stop_event),
            run_operational_scheduler(stop_event),
        )
    finally:
        await close_async_engine()
        logger.info('PipeSight Task Worker 资源已释放。')


def main() -> None:
    """启动 PipeSight 持久任务 Worker。"""
    try:
        asyncio.run(_run_worker())
    except KeyboardInterrupt:
        logger.info('PipeSight Task Worker 收到中断信号。')


if __name__ == '__main__':
    main()
