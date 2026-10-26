from datetime import datetime

from sqlalchemy import CHAR, Column, DateTime, Index, Integer, String, UniqueConstraint

from app.infrastructure.services.serialization import SqlalchemyUtil
from config.database import Base
from config.env import DataBaseConfig


class SysConfig(Base):
    """
    参数配置表
    """

    __api_field_map__ = {
        'config_id': 'id',
        'config_name': 'name',
        'config_key': 'key',
        'config_value': 'value',
        'config_type': 'type',
        'create_by': 'created_by',
        'create_time': 'created_at',
        'update_by': 'updated_by',
        'update_time': 'updated_at',
    }

    __tablename__ = 'sys_config'
    __table_args__ = (
        UniqueConstraint('key', name='uk_settings_config_key'),
        Index('idx_settings_type', 'type'),
        {'comment': '参数配置表'},
    )

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True, comment='参数主键')
    name = Column(String(100), nullable=True, server_default="''", comment='参数名称')
    key = Column(String(100), nullable=True, server_default="''", comment='参数键名')
    value = Column(String(500), nullable=True, server_default="''", comment='参数键值')
    type = Column(CHAR(1), nullable=True, server_default='N', comment='系统内置（Y是 N否）')
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
