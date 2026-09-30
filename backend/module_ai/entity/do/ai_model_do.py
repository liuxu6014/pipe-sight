from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from config.database import Base
from config.env import DataBaseConfig
from utils.common_util import SqlalchemyUtil


class AiModels(Base):
    """
    AI模型表
    """

    __tablename__ = 'ai_models'
    __table_args__ = (
        UniqueConstraint('user_id', 'provider', 'model_code', name='uk_ai_models_owner_provider_code'),
        CheckConstraint('max_tokens IS NULL OR max_tokens > 0', name='ck_ai_models_max_tokens'),
        CheckConstraint('temperature IS NULL OR temperature BETWEEN 0 AND 2', name='ck_ai_models_temperature'),
        CheckConstraint("support_reasoning IN ('Y', 'N')", name='ck_ai_models_support_reasoning'),
        CheckConstraint("support_images IN ('Y', 'N')", name='ck_ai_models_support_images'),
        CheckConstraint("status IN ('0', '1')", name='ck_ai_models_status'),
        Index('idx_ai_models_type_status_sort', 'model_type', 'status', 'model_sort'),
        Index('idx_ai_models_owner', 'user_id'),
        {'comment': 'AI模型表'},
    )

    model_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='模型主键')
    model_code = Column(String(100), nullable=False, comment='模型编码')
    model_name = Column(
        String(100),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='模型名称',
    )
    provider = Column(String(50), nullable=False, comment='提供商')
    model_sort = Column(Integer, nullable=False, comment='显示顺序')
    api_key = Column(
        String(255),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='API Key',
    )
    base_url = Column(
        String(255),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='Base URL',
    )
    model_type = Column(
        String(50),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='模型类型',
    )
    max_tokens = Column(Integer, nullable=True, comment='最大输出token')
    temperature = Column(Float, nullable=True, comment='默认温度')
    support_reasoning = Column(CHAR(1), server_default='N', comment='是否支持推理')
    support_images = Column(CHAR(1), server_default='N', comment='是否支持图片')
    status = Column(CHAR(1), server_default='0', comment='模型状态')
    user_id = Column(BigInteger, ForeignKey('sys_user.user_id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    create_by = Column(String(64), nullable=True, server_default="''", comment='创建者')
    create_time = Column(DateTime, nullable=True, default=datetime.now, comment='创建时间')
    update_by = Column(String(64), nullable=True, server_default="''", comment='更新者')
    update_time = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    remark = Column(
        String(500),
        nullable=True,
        server_default=SqlalchemyUtil.get_server_default_null(DataBaseConfig.db_type),
        comment='备注',
    )
