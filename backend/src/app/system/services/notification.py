from app.infrastructure.services.logging_support import logger


class SmsCodeNotifier:
    """短信验证码通知适配器。

    当前实现仅记录验证码日志，生产环境可在此处替换为真实短信供应商适配器。
    """

    @staticmethod
    def notify(sms_code: str) -> None:
        logger.info(f'短信验证码为{sms_code}')
