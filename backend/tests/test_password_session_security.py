"""Credential changes are exercised with private in-memory DAO/cache doubles."""

import inspect
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.system.models.role import SysRole
from app.system.models.user import SysUser
from app.system.repositories.users import UserDao
from app.system.schemas.user import EditUserModel, ResetPasswordModel, ResetUserModel
from app.system.services.authentication import LoginService
from app.system.services.passwords import PasswordService
from app.system.services.users import UserService
from common.enums.cache import RedisInitKeyConfig
from config.env import AppConfig, JwtConfig
from exceptions.exception import AuthException, ModelValidatorException, ServiceException


@pytest.fixture
def accounts(monkeypatch):
    monkeypatch.setattr(AppConfig, 'app_same_time_login', True)
    users = {
        user_id: SysUser(
            id=user_id,
            username=f'audit_{user_id}',
            nickname=f'Audit {user_id}',
            password_hash=PasswordService.get_password_hash('OldPassword12'),
            password_updated_at=datetime(2026, 1, 1),
            status='0',
        )
        for user_id in (42, 43)
    }
    role = SysRole(id=7, name='Reader', code='common', data_scope='5', status='0')

    async def find(_db, user_id):
        return {'user_basic_info': users[int(user_id)], 'user_role_info': [role], 'user_menu_info': []}

    async def edit(_db, values):
        user = users[values['user_id']]
        if 'password' in values:
            user.password_hash = values['password']
        if 'pwd_update_date' in values:
            user.password_updated_at = values['pwd_update_date']

    monkeypatch.setattr(UserDao, 'get_user_by_id', AsyncMock(side_effect=find))
    monkeypatch.setattr(UserDao, 'get_user_detail_by_id', AsyncMock(side_effect=find))
    monkeypatch.setattr(UserDao, 'edit_user_dao', AsyncMock(side_effect=edit))
    monkeypatch.setattr(UserDao, 'get_user_by_name', AsyncMock(return_value=users[42]))
    cache = {}

    async def get(key):
        return cache.get(key)

    async def set_value(key, value, **_kwargs):
        cache[key] = value

    async def delete(key):
        return cache.pop(key, None) is not None

    async def compare_cache(_script, _count, key, expected, *expire_seconds):
        if cache.get(key) != expected:
            return 0
        return 1 if expire_seconds else await delete(key)

    redis = SimpleNamespace(
        get=AsyncMock(side_effect=get),
        set=AsyncMock(side_effect=set_value),
        delete=AsyncMock(side_effect=delete),
        eval=AsyncMock(side_effect=compare_cache),
    )
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    async def issue(user_id, session_id):
        token = await LoginService.create_access_token(
            {
                'user_id': str(user_id),
                'session_id': session_id,
                'credential_version': LoginService.credential_version(users[user_id]),
            }
        )
        cache[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}'] = token
        return token

    return SimpleNamespace(users=users, cache=cache, redis=redis, db=db, issue=issue)


@pytest.mark.parametrize(
    'body',
    [
        {'newPassword': 'NewPassword12'},
        {'oldPassword': None, 'newPassword': 'NewPassword12'},
        {'oldPassword': '', 'newPassword': 'NewPassword12'},
        {'oldPassword': '  ', 'newPassword': 'NewPassword12'},
        {'oldPassword': 'OldPassword12'},
        {'oldPassword': 'OldPassword12', 'newPassword': None},
        {'oldPassword': 'OldPassword12', 'newPassword': '  '},
        {'oldPassword': 'OldPassword12', 'newPassword': 'short'},
        {'oldPassword': 'OldPassword12', 'newPassword': 'x' * 21},
    ],
)
def test_self_password_request_requires_old_password_and_ui_length_policy(body):
    with pytest.raises((ValidationError, ModelValidatorException)):
        ResetPasswordModel(**body)


@pytest.mark.asyncio
@pytest.mark.parametrize('old', [None, '', ' ', 'wrong'])
async def test_self_password_service_cannot_skip_old_password(accounts, old):
    with pytest.raises(ServiceException):
        await UserService.change_password_services(
            accounts.db, ResetUserModel(userId=42, oldPassword=old, password='NewPassword12')
        )
    UserDao.edit_user_dao.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_change_revokes_every_old_session_without_affecting_other_user(accounts):
    first = await accounts.issue(42, 'device-one')
    second = await accounts.issue(42, 'device-two')
    other = await accounts.issue(43, 'other-user')
    await LoginService.get_current_user(accounts.redis, first, accounts.db)
    await UserService.change_password_services(
        accounts.db, ResetUserModel(userId=42, oldPassword='OldPassword12', password='NewPassword12')
    )
    assert PasswordService.verify_password('NewPassword12', accounts.users[42].password_hash)
    for token in (first, second):
        with pytest.raises(AuthException):
            await LoginService.get_current_user(accounts.redis, token, accounts.db)
    assert (await LoginService.get_current_user(accounts.redis, other, accounts.db)).user.user_id == 43
    renewed = await accounts.issue(42, 'new-login')
    assert (await LoginService.get_current_user(accounts.redis, renewed, accounts.db)).user.user_id == 42


@pytest.mark.asyncio
async def test_admin_reset_revokes_tokens_even_with_same_timestamp(accounts, monkeypatch):
    first = await accounts.issue(42, 'device-one')
    monkeypatch.setattr(
        UserService, 'user_detail_services', AsyncMock(return_value=SimpleNamespace(data=SimpleNamespace(user_id=42)))
    )
    await UserService.edit_user_services(
        accounts.db,
        EditUserModel(
            userId=42,
            password=PasswordService.get_password_hash('AdminReset12'),
            pwdUpdateDate=accounts.users[42].password_updated_at,
            type='pwd',
        ),
    )
    with pytest.raises(AuthException):
        await LoginService.get_current_user(accounts.redis, first, accounts.db)


@pytest.mark.asyncio
async def test_legacy_or_wrong_credential_claim_is_rejected_before_cache_refresh(accounts):
    for claim in ({}, {'credential_version': 'incorrect'}, {'credential_version': '无效'}, {'credential_version': []}):
        token = await LoginService.create_access_token({'user_id': '42', 'session_id': 'old', **claim})
        accounts.cache[f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:old'] = token
        with pytest.raises(AuthException):
            await LoginService.get_current_user(accounts.redis, token, accounts.db)
    accounts.redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_login_handler_binds_token_to_authenticated_credential(accounts, monkeypatch):
    from app.system.api.login_controller import login

    monkeypatch.setattr(LoginService, 'authenticate_user', AsyncMock(return_value=[accounts.users[42]]))
    monkeypatch.setattr(UserService, 'edit_user_services', AsyncMock())
    request = Request(
        {
            'type': 'http',
            'method': 'POST',
            'path': '/login',
            'headers': [],
            'client': ('127.0.0.1', 1000),
            'app': SimpleNamespace(state=SimpleNamespace(redis=accounts.redis)),
        }
    )
    form = SimpleNamespace(username='audit_42', password='OldPassword12', code='', uuid='', login_info={})
    await inspect.unwrap(login)(request, form, accounts.db)
    token = next(
        value for key, value in accounts.cache.items() if key.startswith(RedisInitKeyConfig.ACCESS_TOKEN.key + ':')
    )
    payload = jwt.decode(token, JwtConfig.jwt_secret_key, algorithms=[JwtConfig.jwt_algorithm])
    assert payload['credential_version'] == LoginService.credential_version(accounts.users[42])
    assert 'password_hash' not in payload
    assert (await LoginService.get_current_user(accounts.redis, token, accounts.db)).user.user_id == 42


@pytest.mark.asyncio
async def test_old_single_login_logout_cannot_revoke_new_session(accounts):
    key = f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:42'
    accounts.cache[key] = 'new-session-token'
    assert not await LoginService.logout_services(accounts.redis, '42', expected_token='old-session-token')
    assert accounts.cache[key] == 'new-session-token'
    assert await LoginService.logout_services(accounts.redis, '42', expected_token='new-session-token')
    assert key not in accounts.cache


@pytest.mark.asyncio
@pytest.mark.parametrize('code,stored', [(None, None), ('', ''), ('123456', None), ('wrong', '123456')])
async def test_inactive_recovery_service_cannot_accept_empty_or_wrong_code(accounts, code, stored):
    accounts.cache[f'{RedisInitKeyConfig.SMS_CODE.key}:recovery'] = stored
    outcome = await LoginService.forget_user_services(
        accounts.redis,
        accounts.db,
        ResetUserModel(userName='audit_42', password='NewPassword12', sessionId='recovery', smsCode=code),
    )
    assert not outcome.is_success
    UserDao.edit_user_dao.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_hashes_once_consumes_code_and_revokes_old_session(accounts):
    old = await accounts.issue(42, 'old-device')
    key = f'{RedisInitKeyConfig.SMS_CODE.key}:recovery'
    accounts.cache[key] = json.dumps({'code': '123456', 'user_id': 42})
    outcome = await LoginService.forget_user_services(
        accounts.redis,
        accounts.db,
        ResetUserModel(userName='audit_42', password='NewPassword12', sessionId='recovery', smsCode='123456'),
    )
    assert outcome.is_success
    assert PasswordService.verify_password('NewPassword12', accounts.users[42].password_hash)
    assert key not in accounts.cache
    with pytest.raises(AuthException):
        await LoginService.get_current_user(accounts.redis, old, accounts.db)


@pytest.mark.asyncio
async def test_recovery_code_is_bound_to_one_user_and_not_reusable(accounts, monkeypatch):
    key = f'{RedisInitKeyConfig.SMS_CODE.key}:recovery'
    accounts.cache[key] = json.dumps({'code': '123456', 'user_id': 43})
    request = ResetUserModel(userName='audit_42', password='NewPassword12', sessionId='recovery', smsCode='123456')
    assert not (await LoginService.forget_user_services(accounts.redis, accounts.db, request)).is_success
    UserDao.edit_user_dao.assert_not_awaited()
    accounts.cache[key] = json.dumps({'code': '123456', 'user_id': 42})
    accounts.redis.eval.side_effect = None
    accounts.redis.eval.return_value = 0
    assert not (await LoginService.forget_user_services(accounts.redis, accounts.db, request)).is_success
    UserDao.edit_user_dao.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_sms_adapter_does_not_return_code_to_requester(accounts, monkeypatch):
    from app.system.services.notification import SmsCodeNotifier

    notify = []
    monkeypatch.setattr(SmsCodeNotifier, 'notify', notify.append)
    response = await LoginService.get_sms_code_services(
        accounts.redis, accounts.db, ResetUserModel(userName='audit_42')
    )
    assert response.is_success and response.sms_code == ''
    stored = json.loads(accounts.cache[f'{RedisInitKeyConfig.SMS_CODE.key}:{response.session_id}'])
    assert stored == {'code': notify[0], 'user_id': 42}


@pytest.mark.asyncio
@pytest.mark.parametrize('token', ['Bearer', 'Bearer ', 'Bearer  ', 'BearerBearer', 'Bearer\t', 'Bearer invalid'])
async def test_malformed_bearer_tokens_are_auth_failures_not_server_errors(token):
    from app.system.services.authentication import LoginService
    from exceptions.exception import AuthException

    with pytest.raises(AuthException):
        await LoginService.get_current_user(None, token, None)


@pytest.mark.asyncio
@pytest.mark.parametrize('same_time_login', [True, False])
@pytest.mark.parametrize('replacement', [None, 'new-session-token'])
async def test_expiry_refresh_cannot_restore_logout_or_replace_new_login(
    accounts, monkeypatch, same_time_login, replacement
):
    monkeypatch.setattr(AppConfig, 'app_same_time_login', same_time_login)
    token = await accounts.issue(42, 'session-race')
    key = f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{"session-race" if same_time_login else 42}'
    accounts.cache[key] = token

    def concurrent_change():
        if replacement is None:
            accounts.cache.pop(key, None)
        else:
            accounts.cache[key] = replacement

    async def old_read_then_change(request_key):
        original = accounts.cache.get(request_key)
        if request_key == key:
            concurrent_change()
        return original

    async def compare_expire(_script, _count, request_key, expected, seconds):
        assert request_key == key and seconds == JwtConfig.jwt_redis_expire_minutes * 60
        concurrent_change()
        return int(accounts.cache.get(request_key) == expected)

    accounts.redis.get.side_effect = old_read_then_change
    accounts.redis.eval.side_effect = compare_expire
    with pytest.raises(AuthException):
        await LoginService.get_current_user(accounts.redis, token, accounts.db)
    assert accounts.cache.get(key) == replacement
    accounts.redis.set.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('same_time_login', [True, False])
async def test_expiry_refresh_only_extends_matching_existing_token(accounts, monkeypatch, same_time_login):
    monkeypatch.setattr(AppConfig, 'app_same_time_login', same_time_login)
    token = await accounts.issue(42, 'session-renew')
    key = f'{RedisInitKeyConfig.ACCESS_TOKEN.key}:{"session-renew" if same_time_login else 42}'
    accounts.cache[key] = token
    current = await LoginService.get_current_user(accounts.redis, token, accounts.db)
    assert current.user.user_id == 42 and accounts.cache[key] == token
    accounts.redis.set.assert_not_awaited()
    assert accounts.redis.eval.await_args.args[2:] == (key, token, JwtConfig.jwt_redis_expire_minutes * 60)
