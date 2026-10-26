"""文件输入端口，避免业务服务依赖具体 Web 框架的上传类型。"""

from __future__ import annotations

from typing import Protocol


class UploadFilePort(Protocol):
    """服务层所需的最小异步上传文件协议。"""

    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        """读取上传内容。"""

    async def close(self) -> None:
        """释放上传资源。"""


__all__ = ['UploadFilePort']
