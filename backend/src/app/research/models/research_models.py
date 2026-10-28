"""规范生成实体；展示字段由服务显式适配。"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.business_ids import MAX_BIGINT, business_pk
from app.business_time import BeijingAuditTime, audit_now, server_now
from config.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


json_type = JSON().with_variant(JSONB(), 'postgresql')


class PipelineReport(Base):
    __tablename__ = 'reports'
    __table_args__ = (
        CheckConstraint("type IN ('article','research','daily','weekly','monthly')", name='ck_reports_type'),
        CheckConstraint('version >= 1', name='ck_reports_version'),
        CheckConstraint('length(trim(title))>0', name='ck_reports_title'),
        Index('idx_reports_user_id', 'user_id', text('updated_at DESC'), 'id'),
    )
    id = business_pk()
    user_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='RESTRICT'), nullable=False)
    title = Column(String(1000), nullable=False)
    type = Column(String(32), nullable=False)
    template_id = Column(BigInteger, ForeignKey('templates.id', ondelete='RESTRICT'))
    content = Column(Text, nullable=False, default='', server_default='')
    version = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


class PipelineResearchJob(Base):
    __tablename__ = 'generation_tasks'
    __table_args__ = (
        UniqueConstraint('request_id', name='uk_generation_tasks_request_id'),
        UniqueConstraint('id', 'report_id', name='uk_generation_tasks_id_report_id'),
        CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')", name='ck_generation_tasks_status'
        ),
        CheckConstraint('progress BETWEEN 0 AND 100', name='ck_generation_tasks_progress'),
        CheckConstraint('attempts >= 0', name='ck_generation_tasks_attempts'),
        CheckConstraint("jsonb_typeof(config_snapshot)='object'", name='ck_generation_tasks_config_snapshot').ddl_if(
            dialect='postgresql'
        ),
        CheckConstraint(
            "CASE WHEN jsonb_typeof(materials) = 'array' THEN jsonb_array_length(materials) <= 50 ELSE false END",
            name='ck_generation_tasks_materials',
        ).ddl_if(dialect='postgresql'),
        CheckConstraint(
            'finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at', name='ck_generation_tasks_times'
        ),
        Index('idx_generation_tasks_status', 'status', 'created_at'),
        Index('idx_generation_tasks_schedule_id', 'schedule_id', 'id'),
        Index('idx_generation_tasks_report_id', 'report_id'),
        Index('idx_generation_tasks_lease', 'lease_expires_at', postgresql_where=text('lease_expires_at IS NOT NULL')),
    )
    id = business_pk()
    report_id = Column(BigInteger, ForeignKey('reports.id', ondelete='CASCADE'), nullable=False)
    schedule_id = Column(BigInteger, ForeignKey('digest_schedules.id', ondelete='RESTRICT'))
    request_id = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default='queued', server_default='queued')
    progress = Column(SmallInteger, nullable=False, default=0, server_default='0')
    config_snapshot = Column(json_type, nullable=False, default=dict, server_default=text("'{}'"))
    materials = Column(json_type, nullable=False, default=list, server_default=text("'[]'"))
    result_content = Column(Text)
    error = Column(Text)
    attempts = Column(Integer, nullable=False, default=0, server_default='0')
    lease_expires_at = Column(DateTime(timezone=True))
    execution_token = Column(String(64))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


class PipelineDigestSchedule(Base):
    __tablename__ = 'digest_schedules'
    __table_args__ = (
        CheckConstraint(
            "(frequency='daily' AND weekday IS NULL AND month_day IS NULL) OR (frequency='weekly' AND weekday IS NOT NULL AND weekday BETWEEN 0 AND 6 AND month_day IS NULL) OR (frequency='monthly' AND month_day IS NOT NULL AND month_day BETWEEN 1 AND 31 AND weekday IS NULL)",
            name='ck_digest_schedules_frequency',
        ),
        CheckConstraint('NOT is_enabled OR next_run_at IS NOT NULL', name='ck_digest_schedules_next_run_at'),
        CheckConstraint("last_status IS NULL OR last_status IN ('queued','no_data','skipped','failed')", name='ck_digest_schedules_last_status'),
        CheckConstraint("jsonb_typeof(selection_config)='object'", name='ck_digest_schedules_selection_config').ddl_if(
            dialect='postgresql'
        ),
        CheckConstraint(
            "jsonb_typeof(generation_config)='object'", name='ck_digest_schedules_generation_config'
        ).ddl_if(dialect='postgresql'),
        Index('idx_digest_schedules_next_run_at', 'next_run_at', postgresql_where=text('is_enabled')),
    )
    id = business_pk()
    user_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='RESTRICT'), nullable=False)
    name = Column(String(255), nullable=False)
    template_id = Column(BigInteger, ForeignKey('templates.id', ondelete='RESTRICT'), nullable=False)
    frequency = Column(String(16), nullable=False)
    weekday = Column(SmallInteger)
    month_day = Column(SmallInteger)
    run_time = Column(Time, nullable=False)
    timezone = Column(String(64), nullable=False, default='Asia/Shanghai', server_default='Asia/Shanghai')
    selection_config = Column(json_type, nullable=False, default=dict)
    generation_config = Column(json_type, nullable=False, default=dict, server_default=text("'{}'"))
    is_enabled = Column(Boolean, nullable=False, default=True, server_default='true')
    next_run_at = Column(DateTime(timezone=True))
    last_run_at = Column(BeijingAuditTime(), comment='最近派发检查时间，北京时间，精确到秒')
    last_status = Column(String(16), comment='最近派发结果；生成状态从关联任务读取')
    last_error = Column(Text, comment='最近派发失败原因，脱敏后保存')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


class PipelineWorkspaceItem(Base):
    __tablename__ = 'basket_items'
    __table_args__ = (
        CheckConstraint("action IN ('basket','favorite')", name='ck_basket_items_action'),
        CheckConstraint(
            '(CASE WHEN article_id IS NULL THEN 0 ELSE 1 END + CASE WHEN paper_id IS NULL THEN 0 ELSE 1 END + CASE WHEN file_id IS NULL THEN 0 ELSE 1 END + CASE WHEN report_id IS NULL THEN 0 ELSE 1 END)=1',
            name='ck_basket_items_target',
        ),
        *(
            Index(
                f'uk_basket_items_{target}',
                'user_id',
                'action',
                target,
                unique=True,
                postgresql_where=text(f'{target} IS NOT NULL'),
            )
            for target in ('article_id', 'paper_id', 'file_id', 'report_id')
        ),
    )
    id = Column(
        BigInteger,
        Identity(start=1, increment=1, minvalue=1, maxvalue=MAX_BIGINT, cycle=False, cache=1),
        primary_key=True,
    )
    user_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='CASCADE'), nullable=False)
    action = Column(String(16), nullable=False)
    article_id = Column(BigInteger, ForeignKey('news_articles.id', ondelete='CASCADE'))
    paper_id = Column(BigInteger, ForeignKey('papers.id', ondelete='CASCADE'))
    file_id = Column(BigInteger, ForeignKey('knowledge_files.id', ondelete='CASCADE'))
    report_id = Column(BigInteger, ForeignKey('reports.id', ondelete='CASCADE'))
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())


class PipelineReportExport(Base):
    """沿用导出实体的 Python 名称，唯一物理表是 report_assets。"""

    __tablename__ = 'report_assets'
    __table_args__ = (
        ForeignKeyConstraint(
            ['task_id', 'report_id'],
            ['generation_tasks.id', 'generation_tasks.report_id'],
            ondelete='RESTRICT',
            name='fk_report_assets_task_id_report_id',
        ),
        CheckConstraint("type IN ('image','export')", name='ck_report_assets_type'),
        CheckConstraint("status IN ('queued','running','completed','failed')", name='ck_report_assets_status'),
        CheckConstraint("jsonb_typeof(config_snapshot)='object'", name='ck_report_assets_config_snapshot').ddl_if(
            dialect='postgresql'
        ),
        CheckConstraint('length(trim(mime_type)) > 0', name='ck_report_assets_mime_type'),
        CheckConstraint(
            "status <> 'completed' OR (storage_key IS NOT NULL AND length(trim(storage_key))>0)",
            name='ck_report_assets_storage_key',
        ),
        CheckConstraint(
            "(type='image' AND model_id IS NOT NULL AND prompt IS NOT NULL AND length(trim(prompt))>0) OR (type='export' AND model_id IS NULL AND prompt IS NULL AND position IS NULL)",
            name='ck_report_assets_kind',
        ),
        Index('idx_report_assets_report_id', 'report_id', 'created_at'),
    )
    id = business_pk()
    report_id = Column(BigInteger, ForeignKey('reports.id', ondelete='CASCADE'), nullable=False)
    task_id = Column(BigInteger)
    type = Column(String(16), nullable=False)
    storage_key = Column(Text)
    mime_type = Column(String(128), nullable=False)
    prompt = Column(Text)
    model_id = Column(BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'))
    config_snapshot = Column(json_type, nullable=False, default=dict, server_default=text("'{}'"))
    position = Column(String(100))
    status = Column(String(16), nullable=False, default='queued', server_default='queued')
    error = Column(Text)
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


PipelineReportAsset = PipelineReportExport


class PipelineReportVersion(Base):
    """保留历史恢复；不将历史列重新塞回 reports。"""

    __tablename__ = 'report_versions'
    __table_args__ = (
        UniqueConstraint('report_id', 'version', name='uk_report_versions_report_id_version'),
        CheckConstraint('version>=1', name='ck_report_versions_version'),
        *(
            CheckConstraint(f"jsonb_typeof({column})='{shape}'", name=f'ck_report_versions_{column}').ddl_if(
                dialect='postgresql'
            )
            for column, shape in (
                ('sections', 'array'),
                ('citations', 'array'),
                ('quality_issues', 'array'),
                ('model_snapshot', 'object'),
            )
        ),
    )
    id = Column(
        BigInteger,
        Identity(start=1, increment=1, minvalue=1, maxvalue=MAX_BIGINT, cycle=False, cache=1),
        primary_key=True,
    )
    report_id = Column(BigInteger, ForeignKey('reports.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(1000), nullable=False)
    content = Column(Text, nullable=False)
    sections = Column(json_type, nullable=False, default=list)
    citations = Column(json_type, nullable=False, default=list)
    quality_issues = Column(json_type, nullable=False, default=list)
    model_snapshot = Column(json_type, nullable=False, default=dict)
    source = Column(String(32), nullable=False, default='manual')
    operator_id = Column(BigInteger, ForeignKey('sys_user.id', ondelete='SET NULL'))
    operator_name = Column(String(64), nullable=False, default='')
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())


__all__ = [
    'PipelineDigestSchedule',
    'PipelineReport',
    'PipelineReportAsset',
    'PipelineReportExport',
    'PipelineReportVersion',
    'PipelineResearchJob',
    'PipelineWorkspaceItem',
]
