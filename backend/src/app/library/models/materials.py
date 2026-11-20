"""上传资料：解析结果和用户编辑分别持久化。"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, Column, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.business_ids import business_pk
from app.business_time import BeijingAuditTime, audit_now, server_now
from app.intelligence.models.categories import PipelineCategory  # noqa: F401
from config.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineMaterial(Base):
    __tablename__ = 'knowledge_files'
    __table_args__ = (
        CheckConstraint("status IN ('queued','parsing','ready','failed')", name='ck_knowledge_files_status'),
        CheckConstraint('version>=1', name='ck_knowledge_files_version'),
        CheckConstraint('size>=0', name='ck_knowledge_files_size'),
        CheckConstraint(
            "classification_status IN ('queued','running','completed','failed','not_configured')",
            name='ck_knowledge_files_classification_status',
        ),
        Index('idx_knowledge_files_user_id', 'user_id', text('updated_at DESC')),
        Index('idx_knowledge_files_status_updated_at', 'status', 'updated_at'),
        Index('idx_knowledge_files_classification_queue', 'classification_status', 'id'),
    )
    id = business_pk()
    user_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='RESTRICT'), nullable=False)
    name = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_key = Column(Text, nullable=False)
    mime_type = Column(String(128), nullable=False)
    size = Column(BigInteger, nullable=False)
    hash = Column(String(64), nullable=False)
    extracted_text = Column(Text)
    edited_text = Column(Text)
    version = Column(Integer, nullable=False, default=1, server_default='1')
    status = Column(String(16), nullable=False, default='queued', server_default='queued')
    error = Column(Text)
    category_id = Column(BigInteger, ForeignKey('categories.id', ondelete='RESTRICT'), nullable=True)
    classification_status = Column(
        String(16), nullable=False, default='not_configured', server_default='not_configured'
    )
    classification_error = Column(Text)
    classification_token = Column(String(32))
    classification_updated_at = Column(BeijingAuditTime())
    category = relationship('PipelineCategory', lazy='selectin')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


__all__ = ['PipelineMaterial']
