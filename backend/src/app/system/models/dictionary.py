from datetime import datetime

from sqlalchemy import CHAR, BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.infrastructure.services.serialization import SqlalchemyUtil
from config.database import Base
from config.env import DataBaseConfig


class SysDictType(Base):
    """
    字典类型表
    """

    __api_field_map__ = {
        'dict_id': 'id',
        'dict_name': 'name',
        'dict_type': 'code',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_dict_type'
    __table_args__ = (
        UniqueConstraint('code', name='uk_dict_types_type'),
        Index('idx_dict_types_status', 'status'),
        {'comment': '字典类型表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='字典主键')
    name = Column(String(100), nullable=True, server_default="''", comment='字典名称')
    code = Column(String(100), nullable=True, server_default="''", comment='字典类型')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
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


class SysDictData(Base):
    """
    字典数据表
    """

    __api_field_map__ = {
        'dict_code': 'id',
        'dict_sort': 'sort_order',
        'dict_label': 'label',
        'dict_value': 'value',
        'dict_type': 'type_code',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_dict_data'
    __table_args__ = (
        UniqueConstraint('type_code', 'value', name='uk_dict_items_type_value'),
        Index('idx_dict_items_type_status_sort', 'type_code', 'status', 'sort_order'),
        {'comment': '字典数据表'},
    )

    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='字典编码')
    sort_order = Column(Integer, nullable=True, server_default='0', comment='字典排序')
    label = Column(String(100), nullable=True, server_default="''", comment='字典标签')
    value = Column(String(100), nullable=True, server_default="''", comment='字典键值')
    type_code = Column(
        String(100),
        ForeignKey('sys_dict_type.code', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=True,
        server_default="''",
        comment='字典类型',
    )
    css_class = Column(
        String(100),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='样式属性（其他样式扩展）',
    )
    list_class = Column(
        String(100),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='表格回显样式',
    )
    is_default = Column(CHAR(1), nullable=True, server_default='N', comment='是否默认（Y是 N否）')
    status = Column(CHAR(1), nullable=True, server_default='0', comment='状态（0正常 1停用）')
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
