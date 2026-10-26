"""业务 API 使用的认证依赖与当前用户契约。

实现暂时复用旧系统模块，业务模块只依赖这个稳定入口，后续替换认证
实现时不再需要修改 intelligence、library、research 的控制器。
"""

from app.system.schemas.user import CurrentUserModel
from common.aspect.pre_auth import CurrentUserDependency, PreAuthDependency

__all__ = ['CurrentUserDependency', 'CurrentUserModel', 'PreAuthDependency']
