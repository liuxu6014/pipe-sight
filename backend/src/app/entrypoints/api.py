"""FastAPI API 进程入口。

此入口复用 ``app.bootstrap`` 中的统一应用工厂，API、Worker 和 CLI 共用同一套
启动生命周期。
"""

from __future__ import annotations

import uvicorn

from app.bootstrap import create_app
from config.env import AppConfig

app = create_app()


def main() -> None:
    """启动 FastAPI API 服务。"""
    uvicorn.run(
        app="app.entrypoints.api:create_app",
        host=AppConfig.app_host,
        port=AppConfig.app_port,
        root_path=AppConfig.app_root_path,
        reload=AppConfig.app_reload,
        workers=AppConfig.app_workers,
        factory=True,
    )


if __name__ == "__main__":
    main()
