"""Unverified logout tokens must neither cause a 500 nor revoke a session."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest

from app.system.api import login_controller as module
from config.env import AppConfig, JwtConfig

SUCCESS_CODE = 200


@pytest.mark.asyncio
@pytest.mark.parametrize('token', [None, 'not-a-token', jwt.encode({'user_id': '1'}, 'wrong-test-signing-key-at-least-32-bytes', algorithm='HS256')])
async def test_invalid_logout_is_idempotent_without_touching_redis(token: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    revoke = AsyncMock()
    monkeypatch.setattr(module.LoginService, 'logout_services', revoke)
    response = await module.logout.__wrapped__(SimpleNamespace(), token)
    assert json.loads(response.body)['code'] == SUCCESS_CODE
    revoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_logout_still_revokes_verified_session(monkeypatch: pytest.MonkeyPatch) -> None:
    revoke = AsyncMock()
    monkeypatch.setattr(module.LoginService, 'logout_services', revoke)
    token = jwt.encode({'user_id': '42', 'session_id': 'test-session', 'exp': 1}, JwtConfig.jwt_secret_key, algorithm=JwtConfig.jwt_algorithm)
    redis = object()
    response = await module.logout.__wrapped__(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=redis))), token)
    assert json.loads(response.body)['code'] == SUCCESS_CODE
    revoke.assert_awaited_once_with(redis, 'test-session' if AppConfig.app_same_time_login else '42')
