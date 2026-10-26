"""Canonical SQLAlchemy models owned by the system bounded context."""

from app.system.models.config import SysConfig
from app.system.models.dictionary import SysDictData, SysDictType
from app.system.models.menu import SysMenu
from app.system.models.role import SysRole, SysRoleDept, SysRoleMenu
from app.system.models.user import SysUser, SysUserPost, SysUserRole

__all__ = [
    'SysConfig',
    'SysDictData',
    'SysDictType',
    'SysMenu',
    'SysRole',
    'SysRoleDept',
    'SysRoleMenu',
    'SysUser',
    'SysUserPost',
    'SysUserRole',
]
