from fastapi import Depends, Request, params
from sqlalchemy import ColumnElement, or_

from common.context import RequestContext
from config.database import Base
from utils.dependency_util import DependencyUtil


class GetDataScope:
    """构造不依赖部门树的用户级数据权限条件。"""

    DATA_SCOPE_ALL = '1'
    DATA_SCOPE_SELF = '5'

    def __init__(
        self,
        query_alias: Base,
        user_alias: str | None = 'user_id',
        dept_alias: str | None = None,
    ) -> None:
        self.query_alias = query_alias
        self.user_alias = user_alias
        self.dept_alias = dept_alias

    def __call__(self, request: Request) -> ColumnElement:
        DependencyUtil.check_exclude_routes(request, err_msg='当前路由不在认证规则内，不可使用GetDataScope依赖项')
        current_user = RequestContext.get_current_user()
        if current_user.user.admin or any(
            role.data_scope == self.DATA_SCOPE_ALL for role in current_user.user.role
        ):
            return or_(True)
        if self.user_alias and hasattr(self.query_alias, self.user_alias):
            return getattr(self.query_alias, self.user_alias) == current_user.user.user_id
        return or_(False)


def DataScopeDependency(  # noqa: N802
    query_alias: Base,
    user_alias: str | None = 'user_id',
    dept_alias: str | None = None,
) -> params.Depends:
    """返回全局或仅本人两级数据权限依赖。"""

    return Depends(GetDataScope(query_alias, user_alias, dept_alias))
