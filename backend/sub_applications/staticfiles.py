from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from config.env import UploadConfig


def mount_staticfiles(app: FastAPI) -> None:
    """
    仅挂载明确允许公开访问的静态资源。

    上传目录同时承载内部资料和头像，不能把整个目录暴露为公开静态目录。
    头像仍保持原有 `/profile/avatar/...` 地址；其它上传文件必须经过各自的
    受控下载接口，由业务层校验当前用户和资料权限。
    """
    avatar_path = Path(UploadConfig.UPLOAD_PATH) / 'avatar'
    avatar_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        f'{UploadConfig.UPLOAD_PREFIX}/avatar',
        StaticFiles(directory=str(avatar_path)),
        name='profile-avatar',
    )
