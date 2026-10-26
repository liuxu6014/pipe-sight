"""3.4/3.13 的来源及运行契约；不维护交接、审核或来源租约。"""

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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    column,
    or_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.business_ids import business_pk
from app.business_time import BeijingAuditTime, audit_as_utc, audit_now, server_now
from config.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


JSON_OBJECT = JSON().with_variant(JSONB(), 'postgresql')
_audit_created = audit_as_utc(column('created_at'))
_available = column('available_at')
_started = column('started_at')
_finished = column('finished_at')
_stopped = column('stop_requested_at')


class PipelineSource(Base):
    __tablename__ = 'data_sources'
    __table_args__ = (
        CheckConstraint("type IN ('website','wechat','paper')", name='ck_data_sources_type'),
        CheckConstraint('length(trim(name)) > 0 AND length(trim(adapter)) > 0', name='ck_data_sources_names'),
        CheckConstraint('cron IS NULL OR length(trim(cron)) > 0', name='ck_data_sources_cron'),
        CheckConstraint(
            '(is_enabled AND cron IS NOT NULL AND next_run_at IS NOT NULL) OR '
            '((NOT is_enabled OR cron IS NULL) AND next_run_at IS NULL)',
            name='ck_data_sources_cursor',
        ),
        CheckConstraint("jsonb_typeof(config) = 'object'", name='ck_data_sources_config').ddl_if(dialect='postgresql'),
        Index(
            'idx_data_sources_next_run_at',
            'next_run_at',
            postgresql_where=text('is_enabled AND cron IS NOT NULL'),
            sqlite_where=text('is_enabled AND cron IS NOT NULL'),
        ),
        {'comment': '来源及采集配置'},
    )
    id = business_pk()
    name = Column(String(255), nullable=False)
    type = Column(String(16), nullable=False)
    url = Column(Text)
    adapter = Column(String(128), nullable=False)
    cron = Column(String(100))
    timezone = Column(String(64), nullable=False, default='Asia/Shanghai', server_default='Asia/Shanghai')
    next_run_at = Column(DateTime(timezone=True))
    config = Column(JSON_OBJECT, nullable=False, default=dict, server_default=text("'{}'"))
    model_id = Column(BigInteger, ForeignKey('ai_models.id', ondelete='RESTRICT'))
    is_enabled = Column(Boolean, nullable=False, default=True, server_default=text('true'))
    created_at = Column(BeijingAuditTime(), nullable=False, default=audit_now, server_default=server_now())
    updated_at = Column(
        BeijingAuditTime(),
        nullable=False,
        default=audit_now,
        server_default=server_now(),
        onupdate=audit_now,
    )


class PipelineCrawlRun(Base):
    __tablename__ = 'collection_runs'
    __table_args__ = (
        UniqueConstraint('request_id', name='uk_collection_runs_request_id'),
        UniqueConstraint('id', 'source_id', name='uk_collection_runs_id_source_id'),
        ForeignKeyConstraint(
            ['parent_id', 'source_id'],
            ['collection_runs.id', 'collection_runs.source_id'],
            name='fk_collection_runs_parent_id_source_id',
            ondelete='RESTRICT',
            match='SIMPLE',
        ),
        CheckConstraint("trigger_type IN ('manual','schedule','retry')", name='ck_collection_runs_trigger_type'),
        CheckConstraint(
            "status IN ('queued','running','stopping','success','failed','cancelled')", name='ck_collection_runs_status'
        ),
        CheckConstraint('length(trim(request_id)) > 0', name='ck_collection_runs_request_id'),
        CheckConstraint(
            "(trigger_type = 'retry' AND parent_id IS NOT NULL) OR (trigger_type <> 'retry' AND parent_id IS NULL)",
            name='ck_collection_runs_parent_trigger',
        ),
        CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_collection_runs_parent_id'),
        CheckConstraint(
            'fetched_count >= 0 AND saved_count >= 0 AND failed_count >= 0 '
            'AND saved_count + failed_count <= fetched_count',
            name='ck_collection_runs_counts',
        ),
        CheckConstraint(
            "status <> 'success' OR (failed_count = 0 AND error IS NULL)", name='ck_collection_runs_success'
        ),
        CheckConstraint(
            "status <> 'failed' OR (error IS NOT NULL AND length(trim(error)) > 0)", name='ck_collection_runs_error'
        ),
        CheckConstraint(
            "status <> 'queued' OR (started_at IS NULL AND finished_at IS NULL "
            'AND execution_token IS NULL AND lease_expires_at IS NULL AND stop_requested_at IS NULL)',
            name='ck_collection_runs_queued',
        ),
        CheckConstraint(
            "status NOT IN ('running','stopping') OR (started_at IS NOT NULL AND finished_at IS NULL)",
            name='ck_collection_runs_active',
        ),
        CheckConstraint(
            "status <> 'running' OR (execution_token IS NOT NULL AND lease_expires_at IS NOT NULL "
            'AND stop_requested_at IS NULL)',
            name='ck_collection_runs_running',
        ),
        CheckConstraint(
            "status NOT IN ('stopping','cancelled') OR stop_requested_at IS NOT NULL", name='ck_collection_runs_stop'
        ),
        CheckConstraint('(execution_token IS NULL) = (lease_expires_at IS NULL)', name='ck_collection_runs_lease_pair'),
        CheckConstraint(
            "status NOT IN ('success','failed','cancelled') OR (finished_at IS NOT NULL "
            'AND execution_token IS NULL AND lease_expires_at IS NULL)',
            name='ck_collection_runs_terminal',
        ),
        CheckConstraint(
            and_(
                _audit_created <= _available,
                or_(_started.is_(None), _started >= _audit_created),
                or_(
                    _finished.is_(None),
                    and_(_finished >= _audit_created, or_(_started.is_(None), _finished >= _started)),
                ),
                or_(_stopped.is_(None), _stopped >= _audit_created),
            ),
            name='ck_collection_runs_times',
        ),
        CheckConstraint(
            "jsonb_typeof(config_snapshot) = 'object' AND jsonb_typeof(checkpoint) = 'object'",
            name='ck_collection_runs_json',
        ).ddl_if(dialect='postgresql'),
        Index(
            'uk_collection_runs_active',
            'source_id',
            unique=True,
            postgresql_where=text("status IN ('queued','running','stopping')"),
            sqlite_where=text("status IN ('queued','running','stopping')"),
        ),
        Index(
            'uk_collection_runs_parent_id',
            'parent_id',
            unique=True,
            postgresql_where=text('parent_id IS NOT NULL'),
            sqlite_where=text('parent_id IS NOT NULL'),
        ),
        Index('idx_collection_runs_source_id', 'source_id', text('created_at DESC'), 'id'),
        Index('idx_collection_runs_status', 'status', 'available_at'),
        Index(
            'idx_collection_runs_lease',
            'lease_expires_at',
            postgresql_where=text("status IN ('running','stopping')"),
        ),
        {'comment': '采集运行、停止与失败重试'},
    )
    id = business_pk()
    source_id = Column(BigInteger, ForeignKey('data_sources.id', ondelete='RESTRICT'), nullable=False)
    parent_id = Column(BigInteger)
    trigger_type = Column(String(16), nullable=False)
    request_id = Column(String(128), nullable=False)
    status = Column(String(16), nullable=False, default='queued', server_default='queued')
    available_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    config_snapshot = Column(JSON_OBJECT, nullable=False, default=dict, server_default=text("'{}'"))
    checkpoint = Column(JSON_OBJECT, nullable=False, default=dict, server_default=text("'{}'"))
    fetched_count = Column(Integer, nullable=False, default=0, server_default='0')
    saved_count = Column(Integer, nullable=False, default=0, server_default='0')
    failed_count = Column(Integer, nullable=False, default=0, server_default='0')
    error = Column(Text)
    stop_requested_at = Column(DateTime(timezone=True))
    execution_token = Column(String(64))
    lease_expires_at = Column(DateTime(timezone=True))
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
