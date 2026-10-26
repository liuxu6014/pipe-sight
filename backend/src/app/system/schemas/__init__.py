"""System API request and response schemas."""

from app.system.schemas.auth import (
    CaptchaCode,
    LoginToken,
    MetaModel,
    RouterModel,
    SmsCode,
    Token,
    UserLogin,
    UserRegister,
)
from app.system.schemas.auth import (
    MenuTreeModel as RouterMenuTreeModel,
)
from app.system.schemas.config import ConfigModel, ConfigPageQueryModel, ConfigQueryModel, DeleteConfigModel
from app.system.schemas.dictionary import (
    DeleteDictDataModel,
    DeleteDictTypeModel,
    DictDataModel,
    DictDataPageQueryModel,
    DictDataQueryModel,
    DictTypeModel,
    DictTypePageQueryModel,
    DictTypeQueryModel,
)
from app.system.schemas.menu import (
    DeleteMenuModel,
    MenuModel,
    MenuQueryModel,
    MenuTreeModel,
)
from app.system.schemas.role import (
    AddRoleModel,
    DeleteRoleModel,
    RoleMenuModel,
    RoleMenuQueryModel,
    RoleModel,
    RolePageQueryModel,
    RoleQueryModel,
)
from app.system.schemas.user import (
    AddUserModel,
    AvatarModel,
    CrudUserRoleModel,
    CurrentUserModel,
    DeleteUserModel,
    EditUserModel,
    ResetPasswordModel,
    ResetUserModel,
    SelectedRoleModel,
    TokenData,
    UserDetailModel,
    UserInfoModel,
    UserModel,
    UserPageQueryModel,
    UserProfileModel,
    UserQueryModel,
    UserRoleModel,
    UserRolePageQueryModel,
    UserRoleQueryModel,
    UserRoleResponseModel,
    UserRowModel,
)

__all__ = [
    'ConfigModel',
    'ConfigPageQueryModel',
    'ConfigQueryModel',
    'DeleteConfigModel',
    'DeleteDictDataModel', 'DeleteDictTypeModel', 'DictDataModel', 'DictDataPageQueryModel',
    'DictDataQueryModel', 'DictTypeModel', 'DictTypePageQueryModel', 'DictTypeQueryModel',
    'AddRoleModel', 'AddUserModel', 'AvatarModel', 'CaptchaCode', 'CrudUserRoleModel',
    'CurrentUserModel', 'DeleteRoleModel', 'DeleteUserModel', 'EditUserModel',
    'DeleteMenuModel', 'LoginToken', 'MenuModel', 'MenuQueryModel', 'MenuTreeModel',
    'MetaModel', 'ResetPasswordModel', 'ResetUserModel', 'RoleMenuModel', 'RoleMenuQueryModel',
    'RoleModel', 'RolePageQueryModel', 'RoleQueryModel', 'SelectedRoleModel',
    'RouterModel', 'RouterMenuTreeModel', 'SmsCode', 'Token', 'TokenData',
    'UserDetailModel', 'UserInfoModel', 'UserLogin', 'UserModel',
    'UserPageQueryModel', 'UserProfileModel', 'UserQueryModel', 'UserRoleModel',
    'UserRolePageQueryModel', 'UserRoleQueryModel', 'UserRoleResponseModel',
    'UserRegister', 'UserRowModel',
]
