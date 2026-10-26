import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.intelligence.api import ai_model_controller
from app.intelligence.services.ai_model_service import AiModelService
from common.aspect.interface_auth import CheckRoleInterfaceAuth, CheckUserInterfaceAuth, RouteDependencyGuard
from common.http.context import RequestContext
from exceptions.exception import PermissionException


@pytest.mark.asyncio
async def test_model_all_includes_disabled_models_for_reactivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    async def fake_list(*args: Any, **_kwargs: Any) -> list[object]:
        captured['query'] = args[1]
        return []

    monkeypatch.setattr(AiModelService, 'get_ai_model_list_services', fake_list)

    response = await ai_model_controller.get_ai_model_all(object(), object())

    assert captured['query'].status is None
    assert json.loads(response.body)['success'] is True


def test_all_model_routes_keep_admin_role_and_explicit_interface_permission() -> None:
    router = ai_model_controller.ai_model_controller
    expected = {
        ('/ai/model/list', 'GET'): 'ai:model:list',
        ('/ai/model/all', 'GET'): 'ai:model:query',
        ('/ai/model', 'POST'): 'ai:model:add',
        ('/ai/model', 'PUT'): 'ai:model:edit',
        ('/ai/model/{model_ids}', 'DELETE'): 'ai:model:remove',
        ('/ai/model/{model_id}', 'GET'): 'ai:model:query',
        ('/ai/model/{model_id}/test', 'POST'): 'ai:model:edit',
    }
    for route in router.routes:
        guards = [dependency.dependency for dependency in route.dependencies]
        assert any(isinstance(guard, CheckRoleInterfaceAuth) and guard.role_key == 'admin' for guard in guards)
        permission = expected[(route.path, next(iter(route.methods)))]
        assert any(isinstance(guard, CheckUserInterfaceAuth) and guard.perm == permission for guard in guards)
    assert len(router.routes) == len(expected)


@pytest.mark.parametrize(
    'roles,allowed', [(['user'], False), ([], False), (['admin'], True), (['user', 'admin'], True)]
)
def test_model_admin_role_guard_accepts_secondary_admin_and_rejects_regular_user(monkeypatch, roles, allowed) -> None:
    # 二级管理员 user_id != 1，旧 UserModel.admin 为 False；应按角色允许。
    user = SimpleNamespace(
        user=SimpleNamespace(user_id=8, admin=False, role=[SimpleNamespace(role_key=role) for role in roles]),
        permissions=['ai:model:query'],
    )
    monkeypatch.setattr(RequestContext, 'get_current_user', staticmethod(lambda: user))
    monkeypatch.setattr(RouteDependencyGuard, 'check_exclude_routes', staticmethod(lambda *args, **kwargs: None))
    route = next(route for route in ai_model_controller.ai_model_controller.routes if route.path == '/ai/model/all')
    guard = next(dep.dependency for dep in route.dependencies if isinstance(dep.dependency, CheckRoleInterfaceAuth))
    if allowed:
        assert guard(None) is True
    else:
        with pytest.raises(PermissionException):
            guard(None)


def test_admin_role_does_not_bypass_model_interface_permission(monkeypatch) -> None:
    user = SimpleNamespace(
        user=SimpleNamespace(user_id=8, admin=False, role=[SimpleNamespace(role_key='admin')]), permissions=[]
    )
    monkeypatch.setattr(RequestContext, 'get_current_user', staticmethod(lambda: user))
    monkeypatch.setattr(RouteDependencyGuard, 'check_exclude_routes', staticmethod(lambda *args, **kwargs: None))
    route = next(route for route in ai_model_controller.ai_model_controller.routes if route.path == '/ai/model/all')
    role = next(dep.dependency for dep in route.dependencies if isinstance(dep.dependency, CheckRoleInterfaceAuth))
    permission = next(
        dep.dependency for dep in route.dependencies if isinstance(dep.dependency, CheckUserInterfaceAuth)
    )
    assert role(None) is True
    with pytest.raises(PermissionException):
        permission(None)
    user.permissions = ['ai:model:query']
    assert permission(None) is True
