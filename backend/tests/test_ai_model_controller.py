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
        ('/ai/model/translation-config', 'GET'): 'ai:model:query',
        ('/ai/model/processing-config', 'GET'): 'ai:model:query',
        ('/ai/model/processing-config', 'PUT'): 'ai:model:edit',
        ('/ai/model/purpose-config/{purpose}', 'GET'): 'ai:model:query',
        ('/ai/model/purpose-config/{purpose}', 'PUT'): 'ai:model:edit',
        ('/ai/model/translation-config', 'PUT'): 'ai:model:edit',
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


@pytest.mark.asyncio
async def test_translation_config_returns_saved_selection_and_surfaces_invalid_model(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.intelligence.schemas.ai_model import TranslationModelSelection

    saved = []

    async def fake_save(db, model_id):
        saved.append(model_id)
        if model_id == 2:
            raise ValueError('翻译模型不可用')
        return {'modelId': str(model_id) if model_id else None}

    async def fake_read(db):
        return {'modelId': '90071992547409931'}

    async def rollback():
        saved.append('rollback')

    monkeypatch.setattr(ai_model_controller, 'save_translation_settings', fake_save)
    monkeypatch.setattr(ai_model_controller, 'translation_settings', fake_read)
    db = SimpleNamespace(rollback=rollback)
    response = await ai_model_controller.get_translation_config(object(), db)
    assert json.loads(response.body)['data'] == {'modelId': '90071992547409931'}
    response = await ai_model_controller.put_translation_config(object(), TranslationModelSelection(modelId=None), db)
    assert json.loads(response.body)['data'] == {'modelId': None}
    with pytest.raises(HTTPException) as error:
        await ai_model_controller.put_translation_config(object(), TranslationModelSelection(modelId=2), db)
    assert error.value.status_code == 422
    assert saved == [None, 2, 'rollback']


def test_translation_get_route_precedes_the_dynamic_model_id_route() -> None:
    from starlette.routing import Match

    route = next(
        route
        for route in ai_model_controller.ai_model_controller.routes
        if route.matches({'type': 'http', 'path': '/ai/model/translation-config', 'method': 'GET'})[0] == Match.FULL
    )
    assert route.endpoint is ai_model_controller.get_translation_config


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


@pytest.mark.asyncio
async def test_processing_config_round_trips_its_own_selection_and_reports_validation_errors(monkeypatch) -> None:
    from fastapi import HTTPException

    from app.intelligence.schemas.ai_model import TranslationModelSelection

    saved = []

    async def read(db):
        return {'modelId': '90071992547409931'}

    async def write(db, identity):
        saved.append(identity)
        if identity == 2:
            raise ValueError('内容处理模型不可用')
        return {'modelId': str(identity) if identity else None}

    async def rollback():
        saved.append('rollback')

    monkeypatch.setattr(ai_model_controller, 'processing_settings', read)
    monkeypatch.setattr(ai_model_controller, 'save_processing_settings', write)
    db = SimpleNamespace(rollback=rollback)
    response = await ai_model_controller.get_processing_config(object(), db)
    assert json.loads(response.body)['data'] == {'modelId': '90071992547409931'}
    response = await ai_model_controller.put_processing_config(object(), TranslationModelSelection(modelId=None), db)
    assert json.loads(response.body)['data'] == {'modelId': None}
    with pytest.raises(HTTPException) as caught:
        await ai_model_controller.put_processing_config(object(), TranslationModelSelection(modelId='2'), db)
    assert caught.value.status_code == 422 and saved == [None, 2, 'rollback']


@pytest.mark.parametrize('setting', ['processing', 'translation'])
def test_literal_setting_routes_dispatch_over_http_instead_of_becoming_integer_model_ids(monkeypatch, setting) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    async def read(db):
        return {'modelId': None}

    async def detail(db, identity):
        return {'modelId': identity}

    monkeypatch.setattr(ai_model_controller, f'{setting}_settings', read)
    monkeypatch.setattr(AiModelService, 'ai_model_detail_services', detail)
    app = FastAPI()
    router = ai_model_controller.ai_model_controller
    for route in router.routes:
        for dependency in route.dependant.dependencies:
            app.dependency_overrides[dependency.call] = lambda: None
    app.include_router(router, prefix='/dev-api')
    with TestClient(app) as client:
        response = client.get(f'/dev-api/ai/model/{setting}-config')
        assert response.status_code == 200
        assert response.json()['data'] == {'modelId': None}
        numeric = client.get('/dev-api/ai/model/123')
        assert numeric.status_code == 200 and numeric.json()['data']['modelId'] == 123


@pytest.mark.parametrize('purpose', ['image', 'digest', 'research'])
def test_generation_purpose_endpoints_round_trip_and_reject_unknown_purposes(monkeypatch, purpose) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    captured = []

    async def read(db, selected):
        assert selected == purpose
        return {'modelId': None}

    async def save(db, selected, identity):
        captured.append((selected, identity))
        return {'modelId': str(identity) if identity is not None else None}

    monkeypatch.setattr(ai_model_controller, 'generation_settings', read)
    monkeypatch.setattr(ai_model_controller, 'save_generation_settings', save)
    app = FastAPI()
    router = ai_model_controller.ai_model_controller
    for route in router.routes:
        for dependency in route.dependant.dependencies:
            app.dependency_overrides[dependency.call] = lambda: None
    app.include_router(router, prefix='/dev-api')
    with TestClient(app) as client:
        path = f'/dev-api/ai/model/purpose-config/{purpose}'
        response = client.get(path)
        assert response.status_code == 200 and response.json()['data'] == {'modelId': None}
        response = client.put(path, json={'modelId': '90071992547409931'})
        assert response.status_code == 200 and response.json()['data']['modelId'] == '90071992547409931'
        response = client.put(path, json={'modelId': None})
        assert response.status_code == 200 and captured == [(purpose, 90071992547409931), (purpose, None)]
        assert client.get('/dev-api/ai/model/purpose-config/unknown').status_code == 422
        assert client.put(path, json={'modelId': False}).status_code == 422
