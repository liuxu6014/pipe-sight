from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, Index, Integer, String

from app.infrastructure.services.serialization import SqlalchemyUtil
from config.database import Base
from config.env import DataBaseConfig


class SysMenu(Base):
    """
    菜单权限表
    """

    __api_field_map__ = {
        'menu_id': 'id',
        'menu_name': 'name',
        'order_num': 'sort_order',
        'menu_type': 'type',
        'perms': 'permissions',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_menu'
    __table_args__ = (
        Index('idx_menus_parent_sort', 'parent_id', 'sort_order'),
        Index('idx_menus_status_visible', 'status', 'visible'),
        Index('idx_menus_perms', 'permissions'),
        {'comment': '菜单权限表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='菜单ID')
    name = Column(String(50), nullable=False, comment='菜单名称')
    parent_id = Column(BigInteger, nullable=True, server_default='0', comment='父菜单ID')
    sort_order = Column(Integer, server_default='0', comment='显示顺序')
    path = Column(String(200), nullable=True, server_default="''", comment='路由地址')
    component = Column(
        String(255),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='组件路径',
    )
    query = Column(
        String(255),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='路由默认查询参数的JSON文本；空值表示无默认参数',
    )
    route_name = Column(String(50), nullable=True, server_default="''", comment='路由名称')
    is_frame = Column(Integer, nullable=True, server_default='1', comment='是否为外链（0是 1否）')
    is_cache = Column(Integer, nullable=True, server_default='0', comment='是否缓存（0缓存 1不缓存）')
    type = Column(CHAR(1), nullable=True, server_default="''", comment='菜单类型（M目录 C菜单 F按钮）')
    visible = Column(CHAR(1), nullable=True, server_default='0', comment='菜单状态（0显示 1隐藏）')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='菜单状态（0正常 1停用）')
    permissions = Column(
        String(100),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='权限标识',
    )
    icon = Column(String(100), nullable=True, server_default='#', comment='菜单图标')
    created_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    updated_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    remark = Column(String(500), nullable=True, server_default="''", comment='备注')
