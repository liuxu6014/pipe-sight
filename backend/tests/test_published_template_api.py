"""Template endpoints are scoped to the current user, not an admin role."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request

from app.intelligence.api.controller import controller
from app.intelligence.services.templates import PipelineTemplateService
from app.system.schemas.user import CurrentUserModel, UserInfoModel
from app.system.services.authentication import LoginService
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import CheckRoleInterfaceAuth
from common.aspect.pre_auth import PreAuth


def current_user(user_id: int = 7) -> CurrentUserModel:
    return CurrentUserModel(permissions=[], roles=[], user=UserInfoModel(userId=user_id))


def portal_app() -> FastAPI:
    app = FastAPI()
    app.include_router(controller)
    app.state.redis = object()

    async def signed_in(request: Request) -> None:
        if not request.headers.get('x-test-user'):
            raise HTTPException(status_code=401)

    app.dependency_overrides[DBSessionDependency().dependency] = object
    for route in controller.routes:
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth):
                app.dependency_overrides[dependency.call] = signed_in
    return app


@pytest.mark.asyncio
async def test_published_templates_are_scoped_to_current_user(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = AsyncMock(return_value={'rows': [], 'total': 0})
    monkeypatch.setattr(PipelineTemplateService, 'list_templates', listing)
    initialize = AsyncMock()
    monkeypatch.setattr(PipelineTemplateService, 'install_builtins', initialize)
    monkeypatch.setattr(LoginService, 'get_current_user', AsyncMock(return_value=current_user(7)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.get(
            '/pipeline/templates/published?category=research&publishedOnly=false',
            headers={'x-test-user': 'ordinary-user', 'Authorization': 'Bearer test-token'},
        )
    assert response.status_code == HTTPStatus.OK
    assert listing.await_args.kwargs == {'category': 'research', 'published_only': True, 'user_id': 7}
    assert initialize.await_args.kwargs == {'user_id': 7}


@pytest.mark.asyncio
async def test_template_management_scopes_to_current_user(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = AsyncMock(return_value={'rows': [], 'total': 0})
    monkeypatch.setattr(PipelineTemplateService, 'list_templates', listing)
    initialize = AsyncMock()
    monkeypatch.setattr(PipelineTemplateService, 'install_builtins', initialize)
    monkeypatch.setattr(LoginService, 'get_current_user', AsyncMock(return_value=current_user(8)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.get(
            '/pipeline/templates', headers={'x-test-user': 'ordinary-user', 'Authorization': 'Bearer test-token'}
        )
    assert response.status_code == HTTPStatus.OK
    assert listing.await_args.kwargs == {'category': None, 'user_id': 8, 'include_deleted': True}
    assert initialize.await_args.kwargs == {'user_id': 8}


@pytest.mark.asyncio
async def test_published_templates_still_require_login() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.get('/pipeline/templates/published')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_template_management_is_user_scoped_not_admin_gated() -> None:
    manage = next(
        route for route in controller.routes if route.path == '/pipeline/templates' and 'GET' in route.methods
    )
    picker = next(route for route in controller.routes if route.path == '/pipeline/templates/published')
    assert not any(
        isinstance(dep.call, CheckRoleInterfaceAuth) and dep.call.role_key == 'admin'
        for dep in manage.dependant.dependencies
    )
    assert not any(isinstance(dep.call, CheckRoleInterfaceAuth) for dep in picker.dependant.dependencies)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'method,path,action',
    [
        ('POST', '/pipeline/templates', 'save_draft'),
        ('PUT', '/pipeline/templates/9007199254740993', 'save_draft'),
        ('DELETE', '/pipeline/templates/9007199254740993', 'retire'),
        ('POST', '/pipeline/templates/presets', 'install_builtins'),
        ('POST', '/pipeline/templates/9007199254740993/archive', 'archive'),
        ('POST', '/pipeline/templates/9007199254740993/restore', 'restore'),
    ],
)
async def test_every_template_write_uses_authenticated_owner_and_requires_login(
    monkeypatch, method, path, action
) -> None:
    write = AsyncMock(return_value={'created': 0} if action == 'install_builtins' else {'id': '9007199254740993'})
    monkeypatch.setattr(PipelineTemplateService, action, write)
    monkeypatch.setattr(LoginService, 'get_current_user', AsyncMock(return_value=current_user(8)))
    body = {
        'purpose': 'research',
        'reportType': 'research-demand',
        'name': '个人模板',
        'prompt': '原文依据',
        'userId': 7,
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        anonymous = await client.request(method, path, json=body)
        assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
        write.assert_not_awaited()
        response = await client.request(
            method,
            path,
            json=body,
            headers={
                'x-test-user': 'ordinary-user-8',
                'Authorization': 'Bearer test-token',
            },
        )
    assert response.status_code == HTTPStatus.OK
    assert write.await_args.kwargs['user_id'] == 8
