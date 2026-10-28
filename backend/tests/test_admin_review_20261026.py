"""Admin review regressions. All persistence/transport boundaries are in memory."""
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.intelligence.services.dashboard import IntelligenceDashboardService
from app.research.api.controller import controller
from app.research.repositories.research_repository import ResearchDao
from app.research.services.application import ResearchApplicationService
from app.research.services.reports import ResearchReportService
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import CheckRoleInterfaceAuth, CheckUserInterfaceAuth, RouteDependencyGuard
from common.aspect.pre_auth import PreAuth
from common.http.context import RequestContext
from exceptions.exception import PermissionException, ServiceException


def test_admin_report_route_requires_existing_admin_role_and_list_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    route = next((r for r in controller.routes if r.path == '/pipeline/research/admin/reports'), None)
    assert route is not None
    guards = [dep.call for dep in route.dependant.dependencies]
    role = next(g for g in guards if isinstance(g, CheckRoleInterfaceAuth))
    permission = next(g for g in guards if isinstance(g, CheckUserInterfaceAuth))
    assert role.role_key == 'admin'
    assert permission.perm == 'pipeline:report:list'
    current = SimpleNamespace(user=SimpleNamespace(role=[]), permissions=['pipeline:report:list'])
    monkeypatch.setattr(RequestContext, 'get_current_user', staticmethod(lambda: current))
    monkeypatch.setattr(RouteDependencyGuard, 'check_exclude_routes', staticmethod(lambda *a, **kw: None))
    with pytest.raises(PermissionException):
        role(None)
    current.user.role = [SimpleNamespace(role_key='admin')]
    assert role(None)
    current.permissions = []
    with pytest.raises(PermissionException):
        permission(None)
    current.permissions = ['pipeline:report:list']
    assert permission(None)


@pytest.mark.asyncio
async def test_admin_repository_selects_all_owners_but_personal_list_stays_scoped() -> None:
    db = SimpleNamespace(scalars=AsyncMock(return_value=[]))
    await ResearchDao.list_admin_reports(db)
    admin_sql = str(db.scalars.await_args.args[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'WHERE' not in admin_sql
    await ResearchDao.list_reports(db, 8)
    personal_sql = str(db.scalars.await_args.args[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'reports.user_id = 8' in personal_sql


@pytest.mark.asyncio
async def test_admin_application_keeps_history_serialization_and_true_total(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    listing = AsyncMock(return_value=rows)
    history = AsyncMock()
    monkeypatch.setattr(ResearchDao, 'list_admin_reports', listing, raising=False)
    monkeypatch.setattr(ResearchReportService, '_load_display_history', history)
    monkeypatch.setattr(ResearchApplicationService, 'report_dict', staticmethod(lambda r: {'id': str(r.id)}))
    result = await ResearchApplicationService.list_admin_reports(object())
    assert result == {'rows': [{'id': '1'}, {'id': '2'}], 'total': 2}
    assert history.await_count == len(rows)


@pytest.mark.asyncio
async def test_management_read_access_does_not_allow_writing_other_owners(monkeypatch: pytest.MonkeyPatch) -> None:
    viewer_id = 8
    owned = AsyncMock(return_value=None)
    monkeypatch.setattr(ResearchDao, 'get_report', owned)
    with pytest.raises(ServiceException):
        await ResearchReportService.update_report(object(), user_id=viewer_id, owner_name='用户', report_id=22,
                                                 payload=SimpleNamespace(), report_serializer=lambda r: r)
    assert owned.await_args.args[2] == viewer_id
    assert owned.await_args.kwargs == {'lock': True}


@pytest.mark.asyncio
@pytest.mark.parametrize('identity,permissions,expected', [
    (None, [], 401), ('user', ['pipeline:report:list'], 403),
    ('admin', [], 403), ('admin', ['pipeline:report:list'], 200),
])
async def test_management_http_boundary_uses_real_guards(
    monkeypatch: pytest.MonkeyPatch, identity: str | None, permissions: list[str], expected: int,
) -> None:
    app = FastAPI()
    app.include_router(controller)
    current = SimpleNamespace(user=SimpleNamespace(role=[SimpleNamespace(role_key=identity)]), permissions=permissions)

    async def signed_in(request: Request) -> None:
        if not identity:
            raise HTTPException(status_code=401)

    @app.exception_handler(PermissionException)
    async def denied(request: Request, error: PermissionException) -> JSONResponse:
        return JSONResponse(status_code=403, content={'detail': 'forbidden'})

    app.dependency_overrides[DBSessionDependency().dependency] = object
    for route in controller.routes:
        for dependency in route.dependant.dependencies:
            if isinstance(dependency.call, PreAuth):
                app.dependency_overrides[dependency.call] = signed_in
    monkeypatch.setattr(RequestContext, 'get_current_user', staticmethod(lambda: current))
    monkeypatch.setattr(RouteDependencyGuard, 'check_exclude_routes', staticmethod(lambda *a, **kw: None))
    owner_id = 9
    listing = AsyncMock(return_value={'rows': [{'id': '22', 'ownerId': owner_id}], 'total': 1})
    monkeypatch.setattr(ResearchApplicationService, 'list_admin_reports', listing)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/pipeline/research/admin/reports')
    assert response.status_code == expected
    assert listing.await_count == (1 if expected == HTTPStatus.OK else 0)
    if expected == HTTPStatus.OK:
        assert response.json()['data']['rows'][0]['ownerId'] == owner_id


def result_rows(values: list[object]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_dashboard_returns_source_names_actual_counts_and_distinct_run_ids() -> None:
    run = SimpleNamespace(id=12, source_id=8, status='success', fetched_count=180, saved_count=150, failed_count=0)
    # The selected run includes its source name; no source ID is displayed as a title.
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        result_rows([]), result_rows([]), result_rows([(run, '科技来源')]),
        MagicMock(scalar_one=lambda: 2), MagicMock(scalar_one=lambda: 3), MagicMock(scalar_one=lambda: 4)
    ]))
    result = await IntelligenceDashboardService.summary(db, date_formatter=str)
    assert result['collect_status'] == [{
        'id': '12', 'name': '科技来源', 'status': 'success',
        'fetched_count': 180, 'saved_count': 150, 'failed_count': 0,
    }]
    sql = str(db.execute.await_args_list[2].args[0])
    assert 'JOIN data_sources' in sql
