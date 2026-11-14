from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.system.schemas.user import CurrentUserModel
from common.aspect.pre_auth import CurrentUserDependency, LoginService, PreAuth
from exceptions.exception import PermissionException


@pytest.mark.asyncio
@pytest.mark.parametrize('resolver', ['preauth', 'current-user'])
@pytest.mark.parametrize(
    ('roles', 'method', 'path', 'allowed'),
    [
        (['auditor'], 'GET', '/monitor/operlog/list', True),
        (['auditor'], 'GET', '/monitor/logininfor/list', True),
        (['auditor'], 'GET', '/system/dict/data/type/sys_oper_type', True),
        (['auditor'], 'GET', '/getRouters', True),
        (['auditor'], 'PUT', '/system/user/profile/updatePwd', True),
        (['auditor'], 'POST', '/monitor/operlog/export', False),
        (['auditor'], 'DELETE', '/monitor/logininfor/clean', False),
        (['auditor', 'common'], 'GET', '/pipeline/knowledge/documents', False),
        (['auditor'], 'GET', '/pipeline/research/admin/reports', False),
        (['auditor'], 'GET', '/system/user/list', False),
        (['admin', 'auditor'], 'GET', '/system/user/list', True),
        (['common'], 'GET', '/pipeline/knowledge/documents', True),
    ],
)
async def test_auditor_scope_is_enforced_for_authenticated_requests(
    monkeypatch, resolver, roles, method, path, allowed
):
    user = CurrentUserModel(roles=roles, permissions=[], user=None)
    monkeypatch.setattr(LoginService, 'get_current_user', AsyncMock(return_value=user))
    request = Request(
        {
            'type': 'http',
            'method': method,
            'path': f'/dev-api{path}',
            'headers': [(b'authorization', b'Bearer test-token')],
            'app': SimpleNamespace(state=SimpleNamespace(redis=None)),
        }
    )

    async def authenticate():
        if resolver == 'preauth':
            return await PreAuth()(request, None)
        return await CurrentUserDependency().dependency(request, 'test-token', None)

    if allowed:
        assert await authenticate() is user
    else:
        with pytest.raises(PermissionException):
            await authenticate()
