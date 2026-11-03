"""Department affiliation round trips and subtree filtering on isolated storage."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Integer, MetaData, create_engine, select, true
from sqlalchemy.orm import Session

from app.system.models.dept import SysDept
from app.system.models.menu import SysMenu
from app.system.models.role import SysRole, SysRoleMenu
from app.system.models.user import SysUser, SysUserRole
from app.system.schemas.dept import DeleteDeptModel
from app.system.schemas.user import AddUserModel, EditUserModel, UserPageQueryModel
from app.system.services.depts import DeptService
from app.system.services.users import UserService
from exceptions.exception import ServiceException, ServiceWarning


class MemorySession:
    def __init__(self, session):
        self.session = session

    def add(self, row):
        self.session.add(row)

    async def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()


@pytest.fixture
def db():
    metadata = MetaData()
    for model in (SysDept, SysUser, SysUserRole, SysRole, SysRoleMenu, SysMenu):
        table = model.__table__.to_metadata(metadata)
        if len(table.primary_key.columns) == 1:
            next(iter(table.primary_key.columns)).type = Integer()
    engine = create_engine('sqlite://')
    metadata.create_all(engine)
    with Session(engine) as session:
        for ident, parent, ancestors in [(1, 0, '0'), (2, 1, '0,1'), (11, 0, '0')]:
            session.add(
                SysDept(
                    dept_id=ident,
                    parent_id=parent,
                    ancestors=ancestors,
                    dept_name=f'部门{ident}',
                    status='0',
                    del_flag='0',
                    order_num=0,
                )
            )
        session.commit()
        yield MemorySession(session)
    engine.dispose()


async def add_user(db, name, department):
    return await UserService.add_user_services(
        db,
        AddUserModel(
            userName=name, nickName=name, password='test-hash', status='0', delFlag='0', deptId=department, roleIds=[]
        ),
    )


async def test_user_department_roundtrip_filter_move_clear_and_delete_guard(db):
    await add_user(db, 'child', 2)
    await add_user(db, 'other', 11)
    await add_user(db, 'unassigned', None)
    result = await UserService.get_user_list_services(db, UserPageQueryModel(deptId=1), true(), True)
    assert result.total == 1
    row = result.rows[0]
    assert row.user_name == 'child' and row.dept.dept_name == '部门2'
    info = await UserService.user_detail_services(db, row.user_id)
    assert info.data.dept_id == 2 and info.data.dept.dept_name == '部门2'
    with pytest.raises(ServiceWarning):
        await DeptService.delete_dept_services(db, DeleteDeptModel(deptIds='2'), true())
    await UserService.edit_user_services(
        db, EditUserModel(userId=row.user_id, userName='child', nickName='child', deptId=11, roleIds=[], role=[])
    )
    result = await UserService.get_user_list_services(db, UserPageQueryModel(deptId=1), true(), True)
    assert result.total == 0
    await UserService.edit_user_services(
        db, EditUserModel(userId=row.user_id, userName='child', nickName='child', deptId=None, roleIds=[], role=[])
    )
    info = await UserService.user_detail_services(db, row.user_id)
    assert info.data.dept_id is None and info.data.dept is None
    all_users = await UserService.get_user_list_services(db, UserPageQueryModel(), true(), True)
    assert all_users.total == 3


async def test_invalid_or_disabled_department_never_creates_user(db):
    with pytest.raises(ServiceException):
        await add_user(db, 'bad', 999)
    dept = db.session.get(SysDept, 2)
    dept.status = '1'
    await db.commit()
    with pytest.raises(ServiceException):
        await add_user(db, 'bad', 2)
    assert not (await db.execute(select(SysUser))).scalars().all()


async def test_profile_cannot_change_department(monkeypatch):
    from app.system.api.user_controller import change_system_user_profile_info
    from app.system.schemas.user import UserInfoModel

    handler = change_system_user_profile_info
    while hasattr(handler, '__wrapped__'):
        handler = handler.__wrapped__
    edit = AsyncMock(return_value=SimpleNamespace(message='更新成功'))
    monkeypatch.setattr(UserService, 'edit_user_services', edit)
    current = SimpleNamespace(user=SimpleNamespace(user_id=7, user_name='test', role_ids='', role=[]))
    await handler(None, UserInfoModel(nickName='新昵称', deptId=11), None, current)
    payload = edit.call_args.args[1]
    assert 'dept_id' not in payload.model_fields_set
    assert payload.user_id == 7
