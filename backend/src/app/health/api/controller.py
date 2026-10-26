"""应用存活与就绪探针。"""

from __future__ import annotations

from typing import Any

from fastapi import Request  # noqa: TC002
from fastapi.responses import JSONResponse
from sqlalchemy import text

from common.http.routing import APIRouterPro
from config.database import AsyncSessionLocal
from config.env import AppConfig

health_controller = APIRouterPro(
    prefix='/health',
    order_num=1,
    tags=['健康检查'],
    include_in_schema=False,
)


@health_controller.get('/live')
async def health_live() -> dict[str, str]:
    """只确认进程已经能够接收请求，不访问外部依赖。"""
    return {'status': 'ok', 'service': 'pipesight-backend', 'version': AppConfig.app_version}


@health_controller.get('/ready')
async def health_ready(request: Request) -> JSONResponse:
    """确认数据库和 Redis 已可用，供编排系统决定是否接收流量。"""
    checks: dict[str, str] = {}

    if AsyncSessionLocal is None:
        checks['postgres'] = 'unavailable'
    else:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text('SELECT 1'))
            checks['postgres'] = 'ok'
        except Exception:
            checks['postgres'] = 'unavailable'

    redis = getattr(request.app.state, 'redis', None)
    if redis is None:
        checks['redis'] = 'unavailable'
    else:
        try:
            await redis.ping()
            checks['redis'] = 'ok'
        except Exception:
            checks['redis'] = 'unavailable'

    ready = all(value == 'ok' for value in checks.values())
    payload: dict[str, Any] = {
        'status': 'ok' if ready else 'not_ready',
        'service': 'pipesight-backend',
        'checks': checks,
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


__all__ = ['health_controller']
