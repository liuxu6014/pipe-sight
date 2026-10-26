"""Canonical routes preserve business actions, authorization and removed workflow boundaries."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.intelligence.api.pipeline_controller import pipeline_controller


def route_map():
    return {
        (re.sub(r'\{[^}]+\}', '{}', route.path), tuple(sorted(route.methods))): route
        for route in pipeline_controller.routes
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('admin', [False, True])
@pytest.mark.parametrize('suffix,method', [('', 'get_report'), ('/versions', 'list_report_versions'),
                                        ('/versions/{version_no}', 'get_report_version'), ('/exports', 'list_report_exports')])
async def test_report_read_routes_derive_scope_from_authenticated_admin(monkeypatch, admin, suffix, method):
    from app.research.api.controller import ResearchApplicationService
    mock = AsyncMock(return_value={})
    monkeypatch.setattr(ResearchApplicationService, method, mock)
    route = next(r for r in pipeline_controller.routes if r.path == '/pipeline/research/reports/{report_id}' + suffix and 'GET' in r.methods)
    args = dict(request=None, report_id=33, query_db=object(),
                current_user=SimpleNamespace(user=SimpleNamespace(user_id=8, admin=admin)))
    if 'version_no' in suffix:
        args['version_no'] = 1
    await route.endpoint(**args)
    assert mock.await_args.kwargs['include_all'] is admin


def test_management_dashboard_requires_administrator_identity():
    route = next(route for route in pipeline_controller.routes if route.path == '/pipeline/dashboard')
    assert any(getattr(dependency.dependency, 'role_key', None) == 'admin' for dependency in route.dependencies)


def test_pipeline_controller_exposes_canonical_action_routes_without_retired_workflow():
    routes = route_map()
    required = {
        ('/pipeline/sources', ('GET',)),
        ('/pipeline/sources', ('POST',)),
        ('/pipeline/sources/{}', ('PUT',)),
        ('/pipeline/sources/{}', ('DELETE',)),
        ('/pipeline/tasks', ('GET',)),
        ('/pipeline/tasks/{}/run', ('POST',)),
        ('/pipeline/tasks/runs/{}', ('GET',)),
        ('/pipeline/tasks/runs/{}/retry', ('POST',)),
        ('/pipeline/tasks/runs/{}/stop', ('POST',)),
        ('/pipeline/categories', ('GET',)),
        ('/pipeline/categories', ('POST',)),
        ('/pipeline/templates', ('GET',)),
        ('/pipeline/templates', ('POST',)),
        ('/pipeline/templates/published', ('GET',)),
        ('/pipeline/knowledge/documents', ('GET',)),
        ('/pipeline/knowledge/documents', ('POST',)),
        ('/pipeline/knowledge/documents/{}', ('GET',)),
        ('/pipeline/knowledge/documents/{}', ('PUT',)),
        ('/pipeline/knowledge/documents/{}', ('DELETE',)),
        ('/pipeline/knowledge/documents/{}/retry', ('POST',)),
        ('/pipeline/workspace', ('GET',)),
        ('/pipeline/workspace/items', ('POST',)),
        ('/pipeline/research/jobs', ('POST',)),
        ('/pipeline/research/jobs/{}', ('GET',)),
        ('/pipeline/research/jobs/{}/cancel', ('POST',)),
        ('/pipeline/research/jobs/{}/retry', ('POST',)),
        ('/pipeline/research/jobs/{}/apply-result', ('POST',)),
        ('/pipeline/research/reports/{}', ('PUT',)),
        ('/pipeline/research/reports/{}/export', ('GET',)),
        ('/pipeline/research/reports/{}/exports', ('POST',)),
        ('/pipeline/research/reports/{}/versions', ('GET',)),
        ('/pipeline/research/reports/{}/versions/{}/restore', ('POST',)),
        ('/pipeline/research/assets/{}/download', ('GET',)),
        ('/pipeline/research/assets/{}/retry', ('POST',)),
        ('/pipeline/research/digest-schedules', ('GET',)),
        ('/pipeline/research/digest-schedules', ('POST',)),
        ('/pipeline/research/digest-schedules/{}', ('PUT',)),
        ('/pipeline/research/digest-schedules/{}/run', ('POST',)),
    }
    assert required <= routes.keys(), required - routes.keys()
    assert len(routes) == len(pipeline_controller.routes), 'Duplicate method/path registration'
    retired = {
        'governance',
        'reviews',
        'handoff',
        'prompts',
        'model-routes',
        'publish',
        'finalize',
        'publications',
        'unpublish',
    }
    assert not any(retired.intersection(path.split('/')) for path, _ in routes)


def test_report_export_route_accepts_binary_format_query():
    route = route_map()['/pipeline/research/reports/{}/export', ('GET',)]
    assert 'file_format' in {param.name for param in route.dependant.query_params}


def test_pipeline_management_routes_require_explicit_authorization():
    routes = route_map()
    for path, method, permission in (
        ('/pipeline/sources', 'GET', 'pipeline:source:list'),
        ('/pipeline/tasks', 'GET', 'pipeline:task:list'),
        ('/pipeline/tasks/{}/run', 'POST', 'pipeline:task:run'),
        ('/pipeline/tasks/runs/{}', 'GET', 'pipeline:task:list'),
        ('/pipeline/tasks/runs/{}/stop', 'POST', 'pipeline:task:run'),
        ('/pipeline/tasks/runs/{}/retry', 'POST', 'pipeline:task:run'),
    ):
        assert any(getattr(dep.dependency, 'perm', None) == permission for dep in routes[path, (method,)].dependencies)
    for path in ('/pipeline/categories', '/pipeline/templates'):
        assert any(getattr(dep.dependency, 'role_key', None) == 'admin' for dep in routes[path, ('POST',)].dependencies)
