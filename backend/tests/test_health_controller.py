from types import SimpleNamespace

import pytest
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from app.health.api import controller as health


class _FakeSession:
    async def __aenter__(self) -> '_FakeSession':
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, _statement: object) -> None:
        return None


class _FakeRedis:
    async def ping(self) -> bool:
        return True


def _request(redis: object) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis=redis)))


@pytest.mark.asyncio
async def test_health_live_does_not_require_dependencies() -> None:
    assert await health.health_live() == {
        'status': 'ok',
        'service': 'pipesight-backend',
        'version': health.AppConfig.app_version,
    }


@pytest.mark.asyncio
async def test_health_ready_reports_postgres_and_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, 'AsyncSessionLocal', _FakeSession)

    response = await health.health_ready(_request(_FakeRedis()))

    assert response.status_code == HTTP_200_OK
    assert response.body == (
        b'{"status":"ok","service":"pipesight-backend","checks":{"postgres":"ok","redis":"ok"}}'
    )


@pytest.mark.asyncio
async def test_health_ready_fails_closed_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, 'AsyncSessionLocal', _FakeSession)

    class BrokenRedis:
        async def ping(self) -> bool:
            raise RuntimeError('redis unavailable')

    response = await health.health_ready(_request(BrokenRedis()))

    assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
    assert b'"status":"not_ready"' in response.body
    assert b'"redis":"unavailable"' in response.body
