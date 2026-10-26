import uuid
from datetime import timedelta

from fastapi import Request, Response

from app.infrastructure.services.logging_support import logger
from app.system.schemas.auth import CaptchaCode
from app.system.services.captcha import CaptchaService
from common.annotation.rate_limit_annotation import ApiRateLimit, ApiRateLimitPreset
from common.enums.cache import RedisInitKeyConfig
from common.http.contracts import ApiNamespace
from common.http.responses import ResponseUtil
from common.http.routing import APIRouterPro
from common.http.schemas import DynamicResponseModel

captcha_controller = APIRouterPro(order_num=2, tags=['验证码模块'])


@captcha_controller.get(
    '/captchaImage',
    summary='获取图片验证码接口',
    description='用于获取图片验证码',
    response_model=DynamicResponseModel[CaptchaCode],
)
@ApiRateLimit(namespace=ApiNamespace.CAPTCHA_IMAGE, preset=ApiRateLimitPreset.ANON_AUTH_CAPTCHA)
async def get_captcha_image(request: Request) -> Response:
    captcha_enabled = (
        await request.app.state.redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.captchaEnabled') == 'true'
    )
    register_enabled = (
        await request.app.state.redis.get(f'{RedisInitKeyConfig.SYS_CONFIG.key}:sys.account.registerUser') == 'true'
    )
    session_id = str(uuid.uuid4())
    captcha_result = await CaptchaService.create_captcha_image_service()
    image = captcha_result[0]
    computed_result = captcha_result[1]
    await request.app.state.redis.set(
        f'{RedisInitKeyConfig.CAPTCHA_CODES.key}:{session_id}', computed_result, ex=timedelta(minutes=2)
    )
    logger.info(f'编号为{session_id}的会话获取图片验证码成功')

    return ResponseUtil.success(
        model_content=CaptchaCode(
            captchaEnabled=captcha_enabled, registerEnabled=register_enabled, img=image, uuid=session_id
        )
    )
