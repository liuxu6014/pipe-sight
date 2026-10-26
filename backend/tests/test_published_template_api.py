from http import HTTPStatus
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request

from app.intelligence.api.controller import controller
from app.intelligence.services.templates import PipelineTemplateService
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import CheckRoleInterfaceAuth, CheckUserInterfaceAuth
from common.aspect.pre_auth import PreAuth


def portal_app() -> FastAPI:
    app = FastAPI()
    app.include_router(controller)

    async def signed_in(request: Request) -> None:
        if not request.headers.get('x-test-user'):
            raise HTTPException(status_code=401)

    async def no_management_permission() -> None:
        raise HTTPException(status_code=403)

    app.dependency_overrides[DBSessionDependency().dependency] = object
    for route in controller.routes:
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth):
                app.dependency_overrides[dependency.call] = signed_in
            elif isinstance(dependency.call, (CheckUserInterfaceAuth, CheckRoleInterfaceAuth)):
                app.dependency_overrides[dependency.call] = no_management_permission
    return app


@pytest.mark.asyncio
async def test_portal_can_read_only_published_templates_without_management_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing = AsyncMock(return_value={'rows': [], 'total': 0})
    monkeypatch.setattr(PipelineTemplateService, 'list_templates', listing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.get(
            '/pipeline/templates/published?category=research&publishedOnly=false',
            headers={'x-test-user': 'ordinary-user'},
        )
    assert response.status_code == HTTPStatus.OK
    assert listing.await_args.kwargs == {'category': 'research', 'published_only': True}


@pytest.mark.asyncio
async def test_published_templates_still_require_login() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.get('/pipeline/templates/published')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_portal_user_cannot_read_template_drafts_or_manage_templates(monkeypatch) -> None:
    listing = AsyncMock(side_effect=AssertionError('ordinary user reached management service'))
    monkeypatch.setattr(PipelineTemplateService, 'list_templates', listing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        for method, path in [
            ('GET', '/pipeline/templates'),
            ('POST', '/pipeline/templates'),
        ]:
            response = await client.request(method, path, headers={'x-test-user': 'ordinary-user'})
            assert response.status_code == HTTPStatus.FORBIDDEN
    listing.assert_not_awaited()


@pytest.mark.asyncio
async def test_removed_template_publish_route_returns_404_for_authenticated_user() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=portal_app()), base_url='http://test') as client:
        response = await client.post(
            '/pipeline/templates/research-test/publish', headers={'x-test-user': 'ordinary-user'}
        )
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_template_management_uses_admin_role_guard_while_public_picker_does_not() -> None:
    manage = next(
        route for route in controller.routes if route.path == '/pipeline/templates' and 'GET' in route.methods
    )
    picker = next(route for route in controller.routes if route.path == '/pipeline/templates/published')
    assert any(
        isinstance(dep.call, CheckRoleInterfaceAuth) and dep.call.role_key == 'admin'
        for dep in manage.dependant.dependencies
    )
    assert not any(isinstance(dep.call, CheckRoleInterfaceAuth) for dep in picker.dependant.dependencies)
