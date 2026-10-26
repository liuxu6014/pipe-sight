"""跨入口复用的 HTTP 安全依赖。"""

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/login')

__all__ = ['oauth2_scheme']
