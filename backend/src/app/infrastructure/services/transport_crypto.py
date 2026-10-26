"""传输层加解密 API 服务，底层协议实现位于基础设施核心模块。"""

from redis import asyncio as aioredis

from app.infrastructure.schemas.transport_crypto import (
    TransportCryptoFrontendConfigModel,
    TransportCryptoMonitorModel,
    TransportCryptoPublicKeyModel,
)
from app.infrastructure.services.transport_crypto_core import TransportCryptoMonitorUtil, TransportCryptoUtil
from exceptions.exception import ServiceWarning


class TransportCryptoService:
    """组装前端加密配置、公钥和运行监控信息。"""

    @classmethod
    async def get_transport_frontend_config_services(cls) -> TransportCryptoFrontendConfigModel:
        return TransportCryptoFrontendConfigModel.model_validate(TransportCryptoUtil.build_frontend_config_payload())

    @classmethod
    async def get_transport_public_key_services(cls) -> TransportCryptoPublicKeyModel:
        try:
            payload = TransportCryptoUtil.build_public_key_payload()
        except ValueError as exc:
            # 未启用或未配置密钥是可预期的运行状态，不能冒泡成未处理的 500。
            raise ServiceWarning(message=str(exc)) from exc
        return TransportCryptoPublicKeyModel.model_validate(payload)

    @classmethod
    async def get_transport_crypto_monitor_info_services(
        cls, redis: aioredis.Redis | None
    ) -> TransportCryptoMonitorModel:
        monitor_info = await TransportCryptoMonitorUtil.get_snapshot(redis)
        return TransportCryptoMonitorModel.model_validate(monitor_info)


__all__ = ['TransportCryptoService']
