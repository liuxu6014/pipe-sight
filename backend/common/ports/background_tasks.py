"""后台任务调度端口，隔离业务服务与具体 Web 框架。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class BackgroundTasksPort(Protocol):
    """服务层所需的最小后台任务调度协议。"""

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """登记一个在当前请求完成后执行的任务。"""


__all__ = ['BackgroundTasksPort']
