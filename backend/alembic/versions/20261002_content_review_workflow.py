"""Add explicit content review fields and immutable review events."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_content_review_workflow'
down_revision = '20260829_drop_legacy_tables'
branch_labels = None
depends_on = None

_CONTENT_TABLES = ('news_articles', 'papers')
_REVIEW_COLUMNS = (
    ('reviewed_by', sa.BigInteger(), None),
    ('reviewed_at', sa.DateTime(), None),
    ('review_reason', sa.Text(), None),
    ('published_at', sa.DateTime(), None),
)


def upgrade() -> None:
    if context.is_offline_mode():
        for table_name in _CONTENT_TABLES:
            for column_name, column_type, _ in _REVIEW_COLUMNS:
                op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))
        op.create_table(
            'pipeline_content_review_events',
            sa.Column('event_id', sa.String(64), primary_key=True, nullable=False),
            sa.Column('content_type', sa.String(16), nullable=False),
            sa.Column('content_id', sa.String(64), nullable=False),
            sa.Column('from_status', sa.String(32), nullable=True),
            sa.Column('to_status', sa.String(32), nullable=False),
            sa.Column('action', sa.String(32), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
                sa.Column('operator_id', sa.BigInteger(), nullable=True),
                sa.ForeignKeyConstraint(['operator_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_review_event_operator'),
            sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
            sa.Column('snapshot_json', sa.JSON(), nullable=False),
            sa.Column('create_time', sa.DateTime(), nullable=False),
            sa.CheckConstraint("content_type IN ('article', 'paper')", name='ck_pipeline_review_event_content_type'),
            sa.CheckConstraint(
                "action IN ('approve', 'reject', 'withdraw')",
                name='ck_pipeline_review_event_action',
            ),
        )
        op.create_index(
            'idx_pipeline_review_event_content_time',
            'pipeline_content_review_events',
            ['content_type', 'content_id', 'create_time'],
        )
        op.create_index(
            'idx_pipeline_review_event_operator_time',
            'pipeline_content_review_events',
            ['operator_id', 'create_time'],
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for table_name in _CONTENT_TABLES:
        if table_name not in tables:
            continue
        columns = {column['name'] for column in inspector.get_columns(table_name)}
        for column_name, column_type, _ in _REVIEW_COLUMNS:
            if column_name not in columns:
                op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))
        existing_indexes = {index['name'] for index in inspector.get_indexes(table_name)}
        index_name = f'idx_{table_name}_review_queue'
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, ['review_status', 'handoff_status', 'update_time'])

    if 'pipeline_content_review_events' not in tables:
        op.create_table(
            'pipeline_content_review_events',
            sa.Column('event_id', sa.String(64), primary_key=True, nullable=False),
            sa.Column('content_type', sa.String(16), nullable=False),
            sa.Column('content_id', sa.String(64), nullable=False),
            sa.Column('from_status', sa.String(32), nullable=True),
            sa.Column('to_status', sa.String(32), nullable=False),
            sa.Column('action', sa.String(32), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('operator_id', sa.BigInteger(), nullable=True),
            sa.ForeignKeyConstraint(['operator_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_review_event_operator'),
            sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
            sa.Column('snapshot_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column('create_time', sa.DateTime(), nullable=False),
            sa.CheckConstraint("content_type IN ('article', 'paper')", name='ck_pipeline_review_event_content_type'),
            sa.CheckConstraint(
                "action IN ('approve', 'reject', 'withdraw')",
                name='ck_pipeline_review_event_action',
            ),
        )
        op.create_index(
            'idx_pipeline_review_event_content_time',
            'pipeline_content_review_events',
            ['content_type', 'content_id', 'create_time'],
        )
        op.create_index(
            'idx_pipeline_review_event_operator_time',
            'pipeline_content_review_events',
            ['operator_id', 'create_time'],
        )


def downgrade() -> None:
    op.drop_index('idx_pipeline_review_event_operator_time', table_name='pipeline_content_review_events')
    op.drop_index('idx_pipeline_review_event_content_time', table_name='pipeline_content_review_events')
    op.drop_table('pipeline_content_review_events')
    for table_name in reversed(_CONTENT_TABLES):
        op.drop_index(f'idx_{table_name}_review_queue', table_name=table_name)
        for column_name, _, _ in reversed(_REVIEW_COLUMNS):
            op.drop_column(table_name, column_name)
