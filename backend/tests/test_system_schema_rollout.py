"""Offline behavior checks for the approved foundation-table rename.

Only a private in-memory SQLite database is used. PostgreSQL SQL is compiled,
never executed; authentication/cache/scheduler dependencies are mocked.
"""

# Fixture adapters deliberately accept varied SQLAlchemy result types.
# ruff: noqa: ANN001, ANN201, ANN202, ANN204, PLR2004, PLC0415

import re
import socket
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.infrastructure.models.audit import SysLogininfor, SysOperLog
from app.infrastructure.models.jobs import SysJob, SysJobLog
from app.infrastructure.repositories.audit_logs import LoginLogDao, OperationLogDao
from app.infrastructure.repositories.job_logs import JobLogDao
from app.infrastructure.repositories.jobs import JobDao
from app.infrastructure.schemas.jobs import JobLogModel, JobModel
from app.infrastructure.schemas.log import LogininforModel, OperLogModel
from app.infrastructure.services.persistence_mapping import PersistenceMapping
from app.infrastructure.services.serialization import CamelCaseUtil, SqlalchemyUtil
from app.system.models.config import SysConfig
from app.system.models.dictionary import SysDictData, SysDictType
from app.system.models.menu import SysMenu
from app.system.models.role import SysRole, SysRoleMenu
from app.system.models.user import SysUser, SysUserRole
from app.system.repositories.configuration import ConfigDao
from app.system.repositories.dictionary import DictDataDao, DictTypeDao
from app.system.repositories.menus import MenuDao
from app.system.repositories.roles import RoleDao
from app.system.repositories.users import UserDao
from app.system.schemas.config import ConfigModel
from app.system.schemas.dictionary import DictDataModel, DictTypeModel
from app.system.schemas.menu import MenuModel
from app.system.schemas.role import RoleMenuModel, RoleModel
from app.system.schemas.user import UserModel, UserRoleModel

MODELS = [
    SysUser,
    SysRole,
    SysMenu,
    SysUserRole,
    SysRoleMenu,
    SysConfig,
    SysDictType,
    SysDictData,
    SysLogininfor,
    SysOperLog,
    SysJob,
    SysJobLog,
]

# The approved correction restores table names only. Column semantics still
# match this appendix, even while its table headings are being updated.
APPENDIX_TABLE_NAMES = {
    'sys_user': 'users',
    'sys_role': 'roles',
    'sys_menu': 'menus',
    'sys_user_role': 'user_roles',
    'sys_role_menu': 'role_menus',
    'sys_config': 'settings',
    'sys_dict_type': 'dict_types',
    'sys_dict_data': 'dict_items',
    'sys_logininfor': 'login_logs',
    'sys_oper_log': 'operation_logs',
    'sys_job': 'scheduled_jobs',
    'sys_job_log': 'job_logs',
}


@pytest.fixture(autouse=True)
def forbid_external_connections(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError('External connections are forbidden in schema rollout tests')

    monkeypatch.setattr(socket, 'create_connection', fail)
    monkeypatch.setattr(socket.socket, 'connect', fail)


class AsyncMemorySession:
    def __init__(self, session):
        self.session = session

    def add(self, obj):
        self.session.add(obj)

    async def execute(self, *args, **kwargs):
        return self.session.execute(*args, **kwargs)

    async def flush(self):
        self.session.flush()


@pytest.fixture
def memory_db():
    engine = create_engine('sqlite://')
    with engine.connect() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
    metadata = SysUser.metadata
    metadata.create_all(engine, tables=[m.__table__ for m in MODELS])
    with Session(engine) as session:
        yield AsyncMemorySession(session)
    engine.dispose()


@pytest.mark.parametrize('model', MODELS)
def test_columns_match_approved_appendix(model):
    document = (Path(__file__).parents[2] / 'output/管网平台精简数据库设计_20261025.md').read_text()
    heading = next(
        '### ' + name + '（现有表：'
        for name in (model.__tablename__, APPENDIX_TABLE_NAMES[model.__tablename__])
        if '### ' + name + '（现有表：' in document
    )
    section = document.split(heading)[1].split('\n### ')[0]
    expected = re.findall(r'^\| `(\w+)` \| `\w+` \|', section, re.M)
    assert list(model.__table__.columns.keys()) == expected
    assert set(inspect(model).attrs.keys()) == set(expected)


def test_relationship_keys_and_foreign_targets():
    assert list(SysUserRole.__table__.primary_key.columns.keys()) == ['user_id', 'role_id']
    assert list(SysRoleMenu.__table__.primary_key.columns.keys()) == ['role_id', 'menu_id']
    assert {f.target_fullname for m in MODELS for f in m.__table__.foreign_keys} == {
        'sys_user.id',
        'sys_role.id',
        'sys_menu.id',
        'sys_dict_type.code',
        'sys_job.id',
    }
    assert not SysMenu.__table__.c.parent_id.foreign_keys
    assert next(iter(SysJobLog.__table__.c.job_id.foreign_keys)).ondelete == 'SET NULL'


@pytest.mark.parametrize('model', MODELS)
def test_foundation_matches_frozen_schema_contract(model):
    from app.schema_contract import load_contract

    contract = next(table for table in load_contract()['tables'] if table['name'] == model.__tablename__)
    assert [column.name for column in model.__table__.columns] == [column['name'] for column in contract['columns']]
    for expected in contract['columns']:
        column = model.__table__.c[expected['name']]
        assert column.nullable == expected['nullable'], (model.__tablename__, column.name)
        assert column.primary_key == expected['primary_key'], (model.__tablename__, column.name)


@pytest.mark.parametrize('model', MODELS)
def test_explicit_api_roundtrip_and_sql_names(model):
    fields = {column.name: None for column in model.__table__.columns}
    api = PersistenceMapping.to_api(model, fields)
    assert PersistenceMapping.to_record(model, api) == fields
    assert CamelCaseUtil.transform_result(model(**fields)) == {
        CamelCaseUtil.snake_to_camel(key): value for key, value in api.items()
    }
    assert SqlalchemyUtil.base_to_dict(model(**fields)) == fields
    sql = str(select(model).compile(dialect=postgresql.dialect()))
    assert f'FROM {model.__tablename__}' in sql


@pytest.mark.asyncio
async def test_user_roles_menus_and_password_persistence(memory_db):
    db = memory_db
    user = await UserDao.add_user_dao(db, UserModel(userId=42, userName='reader', nickName='Reader', password='hash'))
    role = await RoleDao.add_role_dao(
        db, RoleModel(roleId=7, roleName='Reader', roleKey='common', roleSort=1, status='0')
    )
    menu = await MenuDao.add_menu_dao(
        db, MenuModel(menuId=8, menuName='News', menuType='C', perms='news:read', status='0')
    )
    await UserDao.add_user_role_dao(db, UserRoleModel(userId=42, roleId=7))
    await RoleDao.add_role_menu_dao(db, RoleMenuModel(roleId=7, menuId=8))
    await db.flush()
    result = await UserDao.get_user_by_id(db, 42)
    assert result['user_basic_info'].username == 'reader'
    assert result['user_basic_info'].password_hash == 'hash'
    assert [row.id for row in result['user_role_info']] == [7]
    assert [row.permissions for row in result['user_menu_info']] == ['news:read']
    assert [row.id for row in await RoleDao.get_role_menu_dao(db, role)] == [8]
    await UserDao.edit_user_dao(db, {'user_id': 42, 'password': 'new-hash', 'nick_name': 'Renamed', 'role_ids': [7]})
    await RoleDao.edit_role_dao(db, {'role_id': 7, 'role_name': 'Renamed role'})
    await MenuDao.edit_menu_dao(db, {'menu_id': 8, 'perms': 'news:view'})
    db.session.expire_all()
    assert (await UserDao.get_user_by_name(db, 'reader')).password_hash == 'new-hash'
    assert (await RoleDao.get_role_detail_by_id(db, 7)).name == 'Renamed role'
    assert (await MenuDao.get_menu_detail_by_id(db, 8)).permissions == 'news:view'
    assert user.id == 42 and menu.id == 8


@pytest.mark.asyncio
async def test_settings_and_dictionary_code_foreign_key(memory_db):
    db = memory_db
    await ConfigDao.add_config_dao(db, ConfigModel(configId=1, configName='Flag', configKey='flag', configValue='on'))
    await ConfigDao.edit_config_dao(db, {'config_id': 1, 'config_value': 'off'})
    db.session.expire_all()
    assert (await ConfigDao.get_config_detail_by_id(db, 1)).value == 'off'
    await DictTypeDao.add_dict_type_dao(db, DictTypeModel(dictId=2, dictName='Type', dictType='kind', status='0'))
    await DictDataDao.add_dict_data_dao(
        db, DictDataModel(dictCode=3, dictType='kind', dictLabel='One', dictValue='1', status='0')
    )
    await DictTypeDao.edit_dict_type_dao(db, {'dict_id': 2, 'dict_type': 'renamed'})
    db.session.expire_all()
    rows = await DictDataDao.query_dict_data_list(db, 'renamed')
    assert len(rows) == 1 and rows[0].type_code == 'renamed'
    assert CamelCaseUtil.transform_result(rows[0])['dictType'] == 'renamed'


@pytest.mark.asyncio
async def test_job_and_audit_logs_preserve_snapshot_and_api_fields(memory_db):
    db = memory_db
    await JobDao.add_job_dao(
        db,
        JobModel(
            jobId=5, jobName='Scan', jobGroup='default', jobExecutor='default', invokeTarget='app.scan', jobArgs='a,b'
        ),
    )
    log = JobLogDao.add_job_log_dao(
        db.session,
        JobLogModel(
            jobLogId=6,
            jobId=5,
            jobName='Scan',
            jobGroup='default',
            jobExecutor='default',
            invokeTarget='app.scan',
            jobMessage='done',
        ),
    )
    await JobDao.edit_job_dao(db, {'job_name': 'Renamed'}, JobModel(jobId=5, jobName='Scan', jobGroup='default'))
    db.session.expire_all()
    assert (await JobDao.get_job_detail_by_id(db, 5)).name == 'Renamed'
    assert log.name == 'Scan' and log.job_id == 5
    login = await LoginLogDao.add_login_log_dao(
        db, LogininforModel(infoId=9, userName='unknown', ipaddr='127.0.0.1', msg='failed')
    )
    operation = await OperationLogDao.add_operation_log_dao(
        db, OperLogModel(operId=10, operName='reader', operParam='safe', jsonResult='ok', costTime=23)
    )
    assert login.username == 'unknown' and login.message == 'failed'
    assert operation.request_data == 'safe' and operation.duration_ms == 23
    assert CamelCaseUtil.transform_result(operation)['costTime'] == 23
    await JobDao.delete_job_dao(db, JobModel(jobId=5))
    db.session.expire_all()
    assert log.job_id is None and log.name == 'Scan'


@pytest.mark.asyncio
async def test_authentication_uses_canonical_orm_fields(monkeypatch):
    from app.system.schemas.auth import UserLogin
    from app.system.services import authentication as auth

    user = SysUser(id=42, username='reader', nickname='Reader', password_hash='stored', status='0')
    monkeypatch.setattr(auth, 'login_by_account', AsyncMock(return_value=(user,)))
    monkeypatch.setattr(
        auth.PasswordService, 'verify_password', lambda plain, hashed: (plain, hashed) == ('plain', 'stored')
    )
    redis = SimpleNamespace(get=AsyncMock(return_value=None), delete=AsyncMock())
    result = await auth.LoginService.authenticate_user(
        redis, object(), UserLogin(userName='reader', password='plain', captchaEnabled=False), client_ip='127.0.0.1'
    )
    assert result[0].id == 42


def test_cli_config_conversion_uses_target_fields():
    from app.system.schemas import config
    from cli.runtime.config.service import ConfigRuntimeService

    now = datetime(2026, 10, 25, 12)
    record = SysConfig(id=5, name='Setting', key='flag', value='on', type='N', created_at=now)
    dto = ConfigRuntimeService.build_cli_config_model(config, record)
    assert dto.config_id == 5 and dto.config_key == 'flag' and dto.config_value == 'on'
    assert dto.create_time == now


@pytest.mark.asyncio
async def test_current_user_permissions_profile_and_router_use_target_fields(monkeypatch):
    from app.system.services import authentication as auth
    from app.system.services.menus import MenuService
    from app.system.services.users import UserService
    from common.enums.cache import RedisInitKeyConfig

    user = SysUser(id=42, username='reader', nickname='Reader', status='0', password_updated_at=None)
    role = SysRole(id=7, name='Reader role', code='common', data_scope='5', status='0')
    menu = SysMenu(
        id=8,
        name='News',
        parent_id=0,
        sort_order=1,
        type='C',
        permissions='news:read',
        path='news',
        component='News',
        is_frame=1,
        is_cache=0,
        visible='0',
        route_name='News',
    )
    result = {'user_basic_info': user, 'user_role_info': [role], 'user_menu_info': [menu]}
    monkeypatch.setattr(UserDao, 'get_user_by_id', AsyncMock(return_value=result))
    monkeypatch.setattr(UserDao, 'get_user_detail_by_id', AsyncMock(return_value=result))
    token = await auth.LoginService.create_access_token({'user_id': '42', 'session_id': 'session'})

    async def cached_value(key):
        return token if key.startswith(RedisInitKeyConfig.ACCESS_TOKEN.key + ':') else None

    redis = SimpleNamespace(get=AsyncMock(side_effect=cached_value), set=AsyncMock())
    current = await auth.LoginService.get_current_user(redis, token, object())
    assert current.user.user_id == 42 and current.roles == ['common']
    assert current.permissions == ['news:read']
    routers = await auth.LoginService.get_current_user_routers(42, object())
    assert routers[0]['children'][0]['meta']['title'] == 'News'
    assert MenuService.list_to_tree([menu])[0].id == 8
    profile = await UserService.user_profile_services(object(), 42)
    assert profile.role_group == 'Reader role'


def test_audit_sort_fields_resolve_to_canonical_columns():
    assert PersistenceMapping.column(SysOperLog, 'cost_time').name == 'duration_ms'
    assert PersistenceMapping.column(SysLogininfor, 'login_time').name == 'logged_at'
    assert PersistenceMapping.column(SysOperLog, '__dict__') is None
