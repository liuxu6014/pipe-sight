"""PipeSight 持久任务 Worker 入口。

该进程负责数据源采集、生成任务、图片/报告资源和资料解析，不启动
FastAPI 或系统定时任务，避免 API 进程承担长任务调度和执行压力。
"""

from __future__ import annotations

import asyncio
import argparse
import signal

from app.infrastructure.models.registry import register_sqlalchemy_models
from app.infrastructure.services.logging_support import logger
from app.intelligence.tasks.operational_scheduler import run_operational_scheduler
from app.research.tasks.research_job_scheduler import run_persistent_recovery_loop
from config.get_db import close_async_engine, init_create_table
from app.business_ids import parse_business_id

# 独立进程同样只使用已迁移结构，不借助 API 导入顺序或自动建表修补依赖。


async def _run_worker(*, schedule_ids=None) -> None:
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
        if schedule_ids is not None:
            if not schedule_ids:
                raise ValueError('隔离模式至少指定一个自动计划编号')
            logger.info(f'隔离任务 Worker 仅处理自动计划 {schedule_ids}，不运行采集、导出和资料解析队列。')
            await run_persistent_recovery_loop(stop_event, schedule_ids=schedule_ids)
        else:
            await asyncio.gather(
                run_persistent_recovery_loop(stop_event),
                run_operational_scheduler(stop_event),
            )
    finally:
        await close_async_engine()
        logger.info('PipeSight Task Worker 资源已释放。')


def main() -> None:
    """启动 PipeSight 持久任务 Worker。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='dev')
    parser.add_argument('--digest-schedule-id', type=parse_business_id, action='append',
                        help='仅处理指定自动计划及其生成任务；可重复，不运行其他队列')
    args = parser.parse_args()
    try:
        asyncio.run(_run_worker(schedule_ids=args.digest_schedule_id))
    except KeyboardInterrupt:
        logger.info('PipeSight Task Worker 收到中断信号。')


if __name__ == '__main__':
    main()
