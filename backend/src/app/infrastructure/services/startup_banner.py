"""应用启动日志展示。"""

from app.infrastructure.services.logging_support import logger


def log_startup_banner() -> None:
    """记录一次简洁的应用启动标识。"""
    logger.info('🙏 PipeSight 应用启动检查通过')
