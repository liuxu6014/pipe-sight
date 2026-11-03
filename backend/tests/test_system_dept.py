"""Focused native-department behavior on private SQLite; no live DB, Redis or HTTP."""

import socket
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Integer, MetaData, create_engine, false, select, true
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.infrastructure.services.persistence_mapping import PersistenceMapping
from app.system.api.dept_controller import dept_controller
from app.system.models.dept import SysDept
from app.system.models.user import SysUser
from app.system.repositories.depts import DeptDao
from app.system.schemas.dept import DeleteDeptModel, DeptModel
from app.system.services.depts import DeptService
from common.annotation.cache_annotation import ApiCacheManager
from common.annotation.log_annotation import Log, LogQueueService
from common.aspect.data_scope import GetDataScope
from common.aspect.pre_auth import LoginService
from common.http.context import RequestContext
from common.http.contracts import ApiGroup
from config.get_db import get_db
from exceptions.exception import AuthException, PermissionException, ServiceException, ServiceWarning


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Department tests must not connect to external services')

    monkeypatch.setattr(socket.socket, 'connect', blocked)


class MemorySession:
    def __init__(self, session):
        self.s = session

    def add(self, item):
        self.s.add(item)

    async def execute(self, *args, **kwargs):
        return self.s.execute(*args, **kwargs)

    async def flush(self):
        self.s.flush()

    async def commit(self):
        self.s.commit()

    async def rollback(self):
        self.s.rollback()


@pytest.fixture
def db():
    metadata = MetaData()
    # Copy DDL only: do not mutate application metadata to accommodate SQLite auto IDs.
    dept = SysDept.__table__.to_metadata(metadata)
    SysUser.__table__.to_metadata(metadata)
    dept.c.dept_id.type = Integer()
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    metadata.create_all(engine)
    with Session(engine) as session:
        yield MemorySession(session)
    engine.dispose()


def seed(db):
    for identity, parent, ancestors, name, status in [
        (1, 0, '0', '总部', '0'),
        (2, 1, '0,1', '研发', '0'),
        (3, 2, '0,1,2', '平台', '0'),
        (4, 3, '0,1,2,3', '应用', '0'),
        (11, 0, '0', '分部', '0'),
        (12, 11, '0,11', '研发', '0'),
        (20, 0, '0', '停用根', '1'),
        (21, 20, '0,20', '停用子', '1'),
        (22, 21, '0,20,21', '停用孙', '1'),
    ]:
        db.add(
            SysDept(
                dept_id=identity,
                parent_id=parent,
                ancestors=ancestors,
                dept_name=name,
                order_num=identity,
                status=status,
                del_flag='0',
            )
        )
    db.s.commit()


def record(db, identity):
    return db.s.get(SysDept, identity)


def assert_message(error, fragment):
    assert fragment in error.value.message


def test_native_columns_and_postgresql_ddl():
    fields = {
        'dept_id',
        'parent_id',
        'ancestors',
        'dept_name',
        'order_num',
        'leader',
        'phone',
        'email',
        'status',
        'del_flag',
        'create_by',
        'create_time',
        'update_by',
        'update_time',
    }
    assert set(SysDept.__table__.columns.keys()) == fields
    assert PersistenceMapping.to_record(SysDept, {'dept_id': 1, 'dept_name': '甲', 'extra': 9}) == {
        'dept_id': 1,
        'dept_name': '甲',
    }
    ddl = str(CreateTable(SysDept.__table__).compile(dialect=postgresql.dialect()))
    assert 'dept_id BIGSERIAL' in ddl
    assert 'parent_id BIGINT' in ddl
    assert 'find_in_set' not in str(DeptDao.descendant_clause(1).compile(dialect=postgresql.dialect()))


async def test_empty_tree_allows_root_and_ignores_client_owned_fields(db):
    assert await DeptService.get_dept_tree_services(db, DeptModel(), true()) == []
    await DeptService.add_dept_services(
        db,
        DeptModel(
            deptId=500,
            parentId=0,
            deptName=' 新部门 ',
            orderNum=0,
            ancestors='0,99',
            delFlag='2',
        ),
        true(),
    )
    root = db.s.scalar(select(SysDept))
    assert root.dept_id != 500
    assert (root.parent_id, root.ancestors, root.dept_name, root.del_flag, root.status) == (0, '0', '新部门', '0', '0')
    assert db.s.scalar(select(SysUser.id)) is None


@pytest.mark.parametrize('parent', [2, 3, 4])
async def test_self_and_descendant_parents_are_rejected_without_changes(db, parent):
    seed(db)
    with pytest.raises(ServiceException) as error:
        await DeptService.edit_dept_services(db, DeptModel(deptId=2, parentId=parent), true())
    assert_message(error, '循环')
    assert record(db, 2).parent_id == 1
    assert record(db, 4).ancestors == '0,1,2,3'


async def test_reparent_updates_all_descendants_with_token_boundaries(db):
    seed(db)
    await DeptService.edit_dept_services(db, DeptModel(deptId=2, parentId=11, deptName='研究'), true())
    assert record(db, 2).ancestors == '0,11'
    assert record(db, 3).ancestors == '0,11,2'
    assert record(db, 4).ancestors == '0,11,2,3'
    assert record(db, 12).ancestors == '0,11'
    await DeptService.edit_dept_services(db, DeptModel(deptId=2, parentId=0), true())
    assert record(db, 3).ancestors == '0,2'
    assert record(db, 4).ancestors == '0,2,3'


@pytest.mark.parametrize('parent', [20, 21, 22, 999])
async def test_add_rejects_disabled_or_missing_parent(db, parent):
    seed(db)
    with pytest.raises(ServiceException):
        await DeptService.add_dept_services(db, DeptModel(parentId=parent, deptName='新部门', orderNum=0), true())
    assert len(db.s.scalars(select(SysDept)).all()) == 9


async def test_deleted_parent_is_not_usable(db):
    seed(db)
    record(db, 22).del_flag = '2'
    db.s.commit()
    with pytest.raises(ServiceException) as error:
        await DeptService.add_dept_services(db, DeptModel(parentId=22, deptName='新部门', orderNum=0), true())
    assert_message(error, '不存在或已删除')


async def test_native_status_rules_and_ancestor_promotion(db):
    seed(db)
    # Even a normal grandchild under inconsistent disabled direct children blocks disabling.
    record(db, 2).status = '1'
    db.s.commit()
    with pytest.raises(ServiceException) as error:
        await DeptService.edit_dept_services(db, DeptModel(deptId=1, status='1'), true())
    assert_message(error, '未停用')
    assert record(db, 1).status == '0'
    await DeptService.edit_dept_services(db, DeptModel(deptId=22, status='0'), true())
    assert [record(db, identity).status for identity in (20, 21, 22)] == ['0', '0', '0']
    await DeptService.edit_dept_services(db, DeptModel(deptId=4, status='1'), true())
    assert record(db, 4).status == '1'


async def test_move_does_not_silently_enable_disabled_parent(db):
    seed(db)
    with pytest.raises(ServiceException) as error:
        await DeptService.edit_dept_services(db, DeptModel(deptId=4, parentId=20), true())
    assert_message(error, '停用')
    assert record(db, 4).parent_id == 3
    assert record(db, 20).status == '1'


async def test_same_parent_name_unique_including_root_and_partial_edits(db):
    seed(db)
    for parent, name in [(0, '总部'), (1, '研发')]:
        with pytest.raises(ServiceException) as error:
            await DeptService.add_dept_services(db, DeptModel(parentId=parent, deptName=name, orderNum=0), true())
        assert_message(error, '名称已存在')
    with pytest.raises(ServiceException):
        await DeptService.edit_dept_services(db, DeptModel(deptId=2, parentId=11), true())
    with pytest.raises(ServiceException):
        await DeptService.edit_dept_services(db, DeptModel(deptId=11, deptName='总部'), true())
    await DeptService.edit_dept_services(db, DeptModel(deptId=2, deptName='研发'), true())
    await DeptService.add_dept_services(db, DeptModel(parentId=3, deptName='研发', orderNum=0), true())


async def test_tree_list_and_exclusion_keep_native_shape(db):
    seed(db)
    record(db, 12).del_flag = '2'
    db.s.commit()
    tree = await DeptService.get_dept_tree_services(db, DeptModel(), true())
    assert [node['id'] for node in tree] == [1, 11]
    assert tree[0]['children'][0]['children'][0]['label'] == '平台'
    assert 'children' not in tree[1]
    options = await DeptService.get_dept_for_edit_option_services(db, DeptModel(deptId=1), true())
    assert [item['deptId'] for item in options] == [11]
    matches = await DeptService.get_dept_list_services(db, DeptModel(deptName='停用', status='1'), true())
    assert len(matches) == 3
    assert (await DeptService.dept_detail_services(db, 1, true())).dept_name == '总部'
    with pytest.raises(ServiceException):
        await DeptService.dept_detail_services(db, 12, true())


async def test_cyclic_existing_tree_fails_cleanly(db):
    seed(db)
    record(db, 1).parent_id = 4
    db.s.commit()
    with pytest.raises(ServiceException) as error:
        await DeptService.get_dept_tree_services(db, DeptModel(), true())
    assert_message(error, '循环')


@pytest.mark.parametrize('ids', ['1', '4,3', '22,20'])
async def test_delete_children_guard_is_atomic_and_order_independent(db, ids):
    seed(db)
    with pytest.raises(ServiceWarning) as error:
        await DeptService.delete_dept_services(db, DeleteDeptModel(deptIds=ids), true())
    assert_message(error, '下级部门')
    assert all(row.del_flag == '0' for row in db.s.scalars(select(SysDept)))


@pytest.mark.parametrize('status', ['0', '1'])
async def test_even_disabled_users_prevent_department_deletion(db, status):
    seed(db)
    db.add(SysUser(id=101, username='member', nickname='成员', dept_id=4, del_flag='0', status=status))
    db.s.commit()
    with pytest.raises(ServiceWarning) as error:
        await DeptService.delete_dept_services(db, DeleteDeptModel(deptIds='12,4'), true())
    assert_message(error, '存在用户')
    assert record(db, 12).del_flag == record(db, 4).del_flag == '0'


async def test_soft_deleted_user_allows_soft_delete_and_name_reuse(db):
    seed(db)
    db.add(SysUser(id=101, username='deleted', nickname='已删除', dept_id=4, del_flag='2'))
    db.s.commit()
    now = datetime(2026, 11, 3, 10, 30)
    await DeptService.delete_dept_services(db, DeleteDeptModel(deptIds='4', updateBy='admin', updateTime=now), true())
    assert (record(db, 4).del_flag, record(db, 4).update_by, record(db, 4).update_time) == ('2', 'admin', now)
    assert db.s.get(SysUser, 101).dept_id == 4
    await DeptService.add_dept_services(db, DeptModel(parentId=3, deptName='应用', orderNum=0), true())


@pytest.mark.parametrize('ids', ['', '0', '-1', '1,,2', 'abc', '1,999'])
async def test_bad_delete_ids_do_not_mutate(db, ids):
    seed(db)
    with pytest.raises((ServiceException, ServiceWarning)):
        await DeptService.delete_dept_services(db, DeleteDeptModel(deptIds=ids), true())
    assert record(db, 1).del_flag == '0'


async def test_edit_ignores_client_ancestors_delete_and_creation_audit(db):
    seed(db)
    await DeptService.edit_dept_services(
        db,
        DeptModel(
            deptId=4,
            deptName='新版',
            ancestors='0,999',
            delFlag='2',
            createBy='forged',
            updateBy='operator',
        ),
        true(),
    )
    assert record(db, 4).ancestors == '0,1,2,3'
    assert record(db, 4).del_flag == '0'
    assert record(db, 4).create_by != 'forged'
    assert record(db, 4).update_by == 'operator'


async def test_self_scope_cannot_read_or_mutate_any_department(db):
    seed(db)
    assert await DeptService.get_dept_list_services(db, DeptModel(), false()) == []
    assert await DeptService.get_dept_tree_services(db, DeptModel(), false()) == []
    assert await DeptService.get_dept_for_edit_option_services(db, DeptModel(deptId=1), false()) == []
    for operation, argument in [
        (DeptService.add_dept_services, DeptModel(parentId=0, deptName='越权', orderNum=0)),
        (DeptService.edit_dept_services, DeptModel(deptId=4, deptName='越权')),
        (DeptService.delete_dept_services, DeleteDeptModel(deptIds='4')),
        (DeptService.dept_detail_services, 4),
    ]:
        with pytest.raises(ServiceException) as error:
            await operation(db, argument, false())
        assert_message(error, '权限')
    assert record(db, 4).dept_name == '应用'


@pytest.mark.parametrize(
    ('admin', 'scopes', 'allowed'),
    [
        (True, [], True),
        (False, ['1'], True),
        (False, ['5'], False),
        (False, ['2'], False),
        (False, ['3'], False),
        (False, ['4'], False),
        (False, [], False),
    ],
)
def test_real_scope_dependency_does_not_restore_role_department_scope(db, admin, scopes, allowed):
    RequestContext.set_current_user(
        SimpleNamespace(
            user=SimpleNamespace(
                admin=admin,
                user_id=10,
                role=[SimpleNamespace(data_scope=scope) for scope in scopes],
            )
        )
    )
    try:
        request = Request({'type': 'http', 'method': 'GET', 'path': '/system/dept/list', 'headers': []})
        predicate = GetDataScope(SysDept, user_alias=None)(request)
        assert bool(db.s.scalar(select(1).where(predicate))) is allowed
    finally:
        RequestContext.clear_all()


@pytest.fixture
def api(db, monkeypatch):
    app = FastAPI()
    app.state.redis = SimpleNamespace()
    actor = SimpleNamespace(
        user=SimpleNamespace(user_id=10, user_name='operator', admin=False, role=[SimpleNamespace(data_scope='1')]),
        permissions=[],
    )
    login = AsyncMock(return_value=actor)
    evict = AsyncMock(return_value=0)
    monkeypatch.setattr(LoginService, 'get_current_user', login)
    monkeypatch.setattr(Log, '_get_oper_location', AsyncMock(return_value='offline'))
    monkeypatch.setattr(LogQueueService, 'enqueue_operation_log', AsyncMock())
    monkeypatch.setattr(ApiCacheManager, 'clear_namespaces', evict)

    async def memory_db():
        yield db

    async def failure(request, error):
        return JSONResponse({'code': 403, 'msg': error.message}, status_code=403)

    app.dependency_overrides[get_db] = memory_db
    for error in (AuthException, PermissionException, ServiceException):
        app.add_exception_handler(error, failure)
    app.include_router(dept_controller)
    return SimpleNamespace(app=app, actor=actor, login=login, evict=evict)


ROUTES = [
    ('GET', '/system/dept/list', 'list'),
    ('GET', '/system/dept/list/exclude/1', 'list'),
    ('GET', '/system/dept/1', 'query'),
    ('POST', '/system/dept', 'add'),
    ('PUT', '/system/dept', 'edit'),
    ('DELETE', '/system/dept/4', 'remove'),
]


@pytest.mark.parametrize(('method', 'path', 'permission'), ROUTES)
async def test_each_route_requires_login_and_exact_native_permission(api, db, method, path, permission):
    seed(db)
    body = {'deptId': 4, 'parentId': 3, 'deptName': '新名', 'orderNum': 1}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://offline') as client:
        anonymous = await client.request(method, path, json=body)
        assert anonymous.status_code == 403
        api.login.assert_not_awaited()
        api.actor.permissions = ['system:user:edit', 'system:dept:wrong']
        forbidden = await client.request(method, path, json=body, headers={'Authorization': 'Bearer offline'})
        assert forbidden.status_code == 403
        assert '接口权限' in forbidden.json()['msg']
        api.actor.permissions = [f'system:dept:{permission}']
        success = await client.request(method, path, json=body, headers={'Authorization': 'Bearer offline'})
        assert success.status_code == 200, success.text
        assert success.json()['code'] == 200, success.text
    if method != 'GET':
        api.evict.assert_awaited_once_with(api.app.state.redis, ApiGroup.USER_INFO_MUTATION)
    else:
        api.evict.assert_not_awaited()


async def test_api_rejects_self_scope_even_with_dept_permission_and_preserves_cache(api, db):
    seed(db)
    api.actor.user.role = [SimpleNamespace(data_scope='5')]
    api.actor.permissions = ['system:dept:edit', 'system:dept:list', 'system:dept:add', 'system:dept:remove']
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api.app),
        base_url='http://offline',
        headers={'Authorization': 'Bearer offline'},
    ) as client:
        response = await client.get('/system/dept/list')
        assert response.json()['data'] == []
        for method, path in [('PUT', '/system/dept'), ('POST', '/system/dept'), ('DELETE', '/system/dept/4')]:
            response = await client.request(
                method,
                path,
                json={
                    'deptId': 4,
                    'deptName': '越权',
                    'parentId': 0,
                    'orderNum': 0,
                },
            )
            assert response.json()['code'] != 200
    assert record(db, 4).dept_name == '应用'
    api.evict.assert_not_awaited()
