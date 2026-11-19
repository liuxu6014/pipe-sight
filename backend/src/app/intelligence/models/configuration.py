"""模板直接引用模型；旧路由、提示词版本和审批实体退出。"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.business_ids import business_pk
from app.business_time import BeijingAuditTime, audit_now, server_now
from config.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineTemplateVersion(Base):
    """保留导入名供 API 集成，物理实体只有 templates。"""

    __tablename__ = 'templates'
    __table_args__ = (
        UniqueConstraint('user_id', 'preset_key', name='uq_templates_user_preset'),
        CheckConstraint("purpose IN ('article','research','digest')", name='ck_templates_purpose'),
        CheckConstraint(
            "report_type IS NULL OR (purpose = 'research' AND report_type IN ('research-demand','technology-route','project-demand'))",
            name='ck_templates_report_type',
        ),
        CheckConstraint(
            "digest_cadence IS NULL OR (purpose='digest' AND digest_cadence IN ('weekly','monthly','all','daily'))",
            name='ck_templates_digest_cadence',
        ),
        CheckConstraint('length(trim(name)) > 0 AND length(trim(prompt)) > 0', name='ck_templates_name_prompt'),
        CheckConstraint("jsonb_typeof(sections)='array'", name='ck_templates_sections').ddl_if(dialect='postgresql'),
        CheckConstraint(
            "screening_categories IS NULL OR (purpose='digest' AND jsonb_typeof(screening_categories)='array')",
            name='ck_templates_screening_categories',
        ).ddl_if(dialect='postgresql'),
        CheckConstraint("jsonb_typeof(image_config)='object'", name='ck_templates_image_config').ddl_if(
            dialect='postgresql'
        ),
    )
    id = business_pk()
    user_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='RESTRICT'), nullable=False)
    preset_key = Column(String(64), nullable=True)
    deleted_at = Column(BeijingAuditTime(), nullable=True)
    name = Column(String(255), nullable=False)
    purpose = Column(String(16), nullable=False)
    report_type = Column(String(32), nullable=True)
    digest_cadence = Column(String(16), nullable=True, comment='简报适用周期：weekly、monthly、all；daily仅兼容历史')
    description = Column(Text)
    prompt = Column(Text, nullable=False)
    screening_prompt = Column(Text, nullable=True)
    screening_categories = Column(JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), 'postgresql'))
    model_id = Column(BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=True)
    image_model_id = Column(BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'))
    sections = Column(
        JSON().with_variant(JSONB(), 'postgresql'), nullable=False, default=list, server_default=text("'[]'")
    )
    image_config = Column(
        JSON().with_variant(JSONB(), 'postgresql'), nullable=False, default=dict, server_default=text("'{}'")
    )
    is_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


class PipelineModelCallAudit(Base):
    """实际供应商请求的用量/排障记录；不保存正文、密钥或响应原文。"""

    __tablename__ = 'model_calls'
    __table_args__ = (
        CheckConstraint("capability IN ('text_generate','image_generate')", name='ck_model_calls_capability'),
        CheckConstraint("status IN ('success','failed')", name='ck_model_calls_status'),
        CheckConstraint('duration_ms >= 0', name='ck_model_calls_duration_ms'),
        CheckConstraint('input_tokens IS NULL OR input_tokens >= 0', name='ck_model_calls_input_tokens'),
        CheckConstraint('output_tokens IS NULL OR output_tokens >= 0', name='ck_model_calls_output_tokens'),
        Index('idx_model_calls_model_id_created_at', 'model_id', 'created_at'),
        Index('idx_model_calls_task_id_created_at', 'task_id', 'created_at'),
    )
    id = business_pk()
    task_id = Column(BigInteger, ForeignKey('generation_tasks.id', ondelete='SET NULL'), nullable=True)
    model_id = Column(BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'), nullable=False)
    capability = Column(String(32), nullable=False)
    status = Column(String(16), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())


__all__ = ['PipelineModelCallAudit', 'PipelineTemplateVersion']
