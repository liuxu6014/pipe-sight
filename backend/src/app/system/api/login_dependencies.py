"""登录接口的 FastAPI 依赖定义。"""

from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm

from common.http.security import oauth2_scheme


class LoginFormDependency(OAuth2PasswordRequestForm):
    """扩展 OAuth2 表单，承载登录验证码和会话信息。"""

    def __init__(
        self,
        grant_type: str = Form(default=None, pattern='password'),
        username: str = Form(),
        password: str = Form(),
        scope: str = Form(default=''),
        client_id: str | None = Form(default=None),
        client_secret: str | None = Form(default=None),
        code: str | None = Form(default=''),
        uuid: str | None = Form(default=''),
        login_info: dict[str, str] | None = Form(default=None),
    ) -> None:
        super().__init__(
            grant_type=grant_type,
            username=username,
            password=password,
            scope=scope,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.code = code
        self.uuid = uuid
        self.login_info = login_info


__all__ = ['LoginFormDependency', 'oauth2_scheme']
