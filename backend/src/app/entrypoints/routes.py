"""应用路由清单。

业务控制器通过显式清单登记。这样新增、删除或迁移控制器时会留下可审查的
代码变更，不再依赖顶层目录通配扫描。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

from common.http.routing import APIRouterPro, sort_routers

if TYPE_CHECKING:
    from types import ModuleType

CONTROLLER_MODULES: tuple[str, ...] = (
    'app.health.api.controller',
    'app.infrastructure.api.cache_controller',
    'app.system.api.captcha_controller',
    'app.infrastructure.api.file_controller',
    'app.system.api.config_controller',
    'app.system.api.dictionary_controller',
    'app.infrastructure.api.job_controller',
    'app.infrastructure.api.log_controller',
    'app.system.api.login_controller',
    'app.system.api.menu_controller',
    'app.infrastructure.api.online_controller',
    'app.system.api.role_controller',
    'app.infrastructure.api.server_controller',
    'app.infrastructure.api.transport_crypto_controller',
    'app.system.api.user_controller',
    'app.intelligence.api.ai_model_controller',
    'app.research.api.manuscript_controller',
    'app.intelligence.api.pipeline_controller',
)


def _routers_from_module(module: ModuleType) -> list[tuple[str, APIRouter]]:
    routers: list[tuple[str, APIRouter]] = []
    for attr_name, attr in module.__dict__.items():
        # 聚合模块用下划线别名导入子路由。只发现公开属性，避免子路由既被
        # 单独发现又被聚合路由重复挂载。
        if attr_name.startswith('_'):
            continue
        if isinstance(attr, APIRouterPro):
            if attr.auto_register:
                routers.append((attr_name, attr))
        elif isinstance(attr, APIRouter):
            routers.append((attr_name, attr))
    return routers


def register_application_routers(app: FastAPI) -> None:
    """按显式清单加载并注册所有当前 API 控制器。"""
    routers: list[tuple[str, APIRouter]] = []
    for module_name in CONTROLLER_MODULES:
        routers.extend(_routers_from_module(importlib.import_module(module_name)))
    for _name, router in sort_routers(routers):
        app.include_router(router=router)


__all__ = ['CONTROLLER_MODULES', 'register_application_routers']
