from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import mysql

from app.infrastructure.services.serialization import SqlalchemyUtil
from config.database import Base
from config.env import DataBaseConfig


class SysRole(Base):
    """
    角色信息表
    """

    __api_field_map__ = {
        'role_id': 'id',
        'role_name': 'name',
        'role_key': 'code',
        'role_sort': 'sort_order',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_role'
    __table_args__ = (
        UniqueConstraint('code', name='uk_roles_role_key'),
        UniqueConstraint('name', name='uk_roles_role_name'),
        CheckConstraint("data_scope IN ('1', '5')", name='ck_roles_data_scope'),
        CheckConstraint("status IN ('0', '1')", name='ck_roles_status'),
        CheckConstraint("del_flag IN ('0', '2')", name='ck_roles_del_flag'),
        Index('idx_roles_status', 'status', 'del_flag'),
        {'comment': '角色信息表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='角色ID')
    name = Column(String(30), nullable=False, comment='角色名称')
    code = Column(String(100), nullable=False, comment='角色权限字符串')
    sort_order = Column(Integer, nullable=False, comment='显示顺序')
    data_scope = Column(CHAR(1), nullable=True, server_default='1', comment='数据范围（1全部数据 5仅本人）')
    menu_check_strictly = Column(
        SmallInteger().with_variant(mysql.TINYINT(display_width=1), 'mysql'),
        nullable=True,
        server_default='1',
        comment='菜单树选择项是否关联显示',
    )
    status = Column(CHAR(1), nullable=False, comment='角色状态（0正常 1停用）')
    del_flag = Column(CHAR(1), nullable=True, server_default='0', comment='删除标志（0代表存在 2代表删除）')
    created_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    updated_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    remark = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='备注',
    )


class SysRoleDept:
    """已移除的部门数据范围模型兼容占位符，不注册数据库表。"""


class SysRoleMenu(Base):
    """
    角色和菜单关联表
    """

    __api_field_map__ = {}

    __tablename__ = 'sys_role_menu'
    __table_args__ = {'comment': '角色和菜单关联表'}

    role_id = Column(
        BigInteger,
        ForeignKey('sys_role.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='角色ID',
    )
    menu_id = Column(
        BigInteger,
        ForeignKey('sys_menu.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='菜单ID',
    )
