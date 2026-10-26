import pytest

from app.infrastructure.services.transport_crypto import TransportCryptoService
from app.infrastructure.services.transport_crypto_core import TransportCryptoUtil, TransportSecurityUtil
from exceptions.exception import ServiceWarning


@pytest.mark.asyncio
async def test_public_key_configuration_errors_are_reported_as_service_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_configuration_error() -> dict:
        raise ValueError('传输加密密钥尚未配置')

    monkeypatch.setattr(TransportCryptoUtil, 'build_public_key_payload', raise_configuration_error)

    with pytest.raises(ServiceWarning) as error:
        await TransportCryptoService.get_transport_public_key_services()

    assert error.value.message == '传输加密密钥尚未配置'


@pytest.mark.asyncio
async def test_replay_validation_handles_unavailable_redis_explicitly() -> None:
    with pytest.raises(ValueError, match='防重放校验不可用'):
        await TransportSecurityUtil.validate_replay(
            None,
            'kid-1',
            'nonce-1',
            fail_closed=True,
        )

    await TransportSecurityUtil.validate_replay(
        None,
        'kid-1',
        'nonce-2',
        fail_closed=False,
    )


@pytest.mark.asyncio
async def test_replay_validation_rejects_duplicate_nonce() -> None:
    class FakeRedis:
        async def set(self, *_args: object, **_kwargs: object) -> bool:
            return False

    with pytest.raises(ValueError, match='重复请求'):
        await TransportSecurityUtil.validate_replay(
            FakeRedis(),  # type: ignore[arg-type]
            'kid-1',
            'nonce-duplicate',
            fail_closed=True,
        )
