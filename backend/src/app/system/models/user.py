from datetime import datetime

from sqlalchemy import CHAR, BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint

from app.infrastructure.services.serialization import SqlalchemyUtil
from config.database import Base
from config.env import DataBaseConfig


class SysUser(Base):
    """
    用户信息表
    """

    __api_field_map__ = {
        'user_id': 'id',
        'user_name': 'username',
        'nick_name': 'nickname',
        'phonenumber': 'phone',
        'password': 'password_hash',
        'login_date': 'last_login_at',
        'pwd_update_date': 'password_updated_at',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_user'
    __table_args__ = (
        UniqueConstraint('username', name='uk_users_user_name'),
        CheckConstraint("status IN ('0', '1')", name='ck_users_status'),
        CheckConstraint("del_flag IN ('0', '2')", name='ck_users_del_flag'),
        CheckConstraint("sex IN ('0', '1', '2')", name='ck_users_sex'),
        Index('idx_users_status', 'status', 'del_flag'),
        Index('idx_users_phone', 'phone'),
        {'comment': '用户信息表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='用户ID')
    username = Column(String(30), nullable=False, comment='用户账号；软删除后仍保留且不可复用')
    nickname = Column(String(30), nullable=False, comment='用户昵称')
    user_type = Column(String(2), nullable=True, server_default='00', comment='用户类型（00系统用户）')
    email = Column(String(50), nullable=True, server_default="''", comment='用户邮箱')
    phone = Column(String(11), nullable=True, server_default="''", comment='手机号码')
    sex = Column(CHAR(1), nullable=True, server_default='0', comment='用户性别（0男 1女 2未知）')
    avatar = Column(String(100), nullable=True, server_default="''", comment='头像地址')
    password_hash = Column(
        String(100), nullable=True, server_default="''", comment='登录密码的bcrypt加盐哈希；不存储明文密码'
    )
    status = Column(CHAR(1), nullable=True, server_default='0', comment='帐号状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0代表存在 2代表删除）')
    login_ip = Column(String(128), nullable=True, server_default="''", comment='最后登录IP')
    last_login_at = Column(DateTime, nullable=True, comment='最后登录时间')
    password_updated_at = Column(DateTime, nullable=True, comment='密码最后更新时间')
    created_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    created_at = Column(DateTime, nullable=True, comment='创建时间', default=datetime.now)
    updated_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    updated_at = Column(DateTime, nullable=True, comment='更新时间', default=datetime.now, onupdate=datetime.now)
    remark = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='备注',
    )


class SysUserRole(Base):
    """
    用户和角色关联表
    """

    __api_field_map__ = {}

    __tablename__ = 'sys_user_role'
    __table_args__ = {'comment': '用户和角色关联表'}

    user_id = Column(
        BigInteger,
        ForeignKey('sys_user.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='用户ID',
    )
    role_id = Column(
        BigInteger,
        ForeignKey('sys_role.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='角色ID',
    )


class SysUserPost:
    """已移除的岗位关联模型兼容占位符，不注册数据库表。"""
