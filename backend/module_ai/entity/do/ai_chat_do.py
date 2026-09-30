from sqlalchemy import (
    CHAR,
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)

from config.database import Base


class AiChatConfig(Base):
    """
    AI对话配置表
    """

    __tablename__ = 'ai_chat_config'
    __table_args__ = (UniqueConstraint('user_id', name='uk_ai_chat_config_user'),)

    chat_config_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='配置主键')
    user_id = Column(BigInteger, ForeignKey('sys_user.user_id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    temperature = Column(Float, nullable=True, comment='默认温度')
    add_history_to_context = Column(CHAR(1), nullable=True, server_default='0', comment='是否添加历史记录')
    num_history_runs = Column(Integer, nullable=True, comment='历史记录条数')
    system_prompt = Column(Text, nullable=True, comment='系统提示词')
    metrics_default_visible = Column(CHAR(1), nullable=True, server_default='0', comment='默认显示指标')
    vision_enabled = Column(CHAR(1), nullable=True, server_default='1', comment='是否开启视觉')
    image_max_size_mb = Column(Integer, nullable=True, comment='图片最大大小(MB)')
    create_time = Column(DateTime, nullable=True, comment='创建时间')
    update_time = Column(DateTime, nullable=True, comment='更新时间')
