"""Shared prompt-defined category taxonomy for public content and private documents."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.business_ids import business_pk
from app.business_time import BeijingAuditTime, audit_now, server_now
from config.database import Base


class PipelineCategory(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        UniqueConstraint('name', name='uk_categories_name'),
        CheckConstraint("applies_to IN ('news','paper','document','all')", name='ck_categories_applies_to'),
        CheckConstraint('NOT is_enabled OR model_id IS NOT NULL', name='ck_categories_enabled_model'),
        CheckConstraint('length(trim(name)) > 0 AND length(trim(prompt)) > 0', name='ck_categories_name_prompt'),
        {'comment': '管理员定义的单类别及大模型过滤提示词'},
    )
    id = business_pk(comment='类别ID')
    name = Column(String(100), nullable=False, comment='类别名称')
    prompt = Column(Text, nullable=False, comment='过滤及分类提示词')
    model_id = Column(
        BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=True, comment='分类文本模型ID'
    )
    applies_to = Column(
        String(16), nullable=False, default='all', server_default='all', comment='适用内容：news/paper/document/all'
    )
    is_enabled = Column(Boolean, nullable=False, default=True, server_default='true', comment='是否用于新分类')
    sort_order = Column(Integer, nullable=False, default=0, server_default='0', comment='显示顺序')
    created_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        comment='创建时间',
    )
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
        comment='更新时间',
    )
