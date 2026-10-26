"""Add immutable quality-issue governance events."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_quality_issue_audit'
down_revision = '20261003_insighthub_dead_letter'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'pipeline_quality_issue_events',
        sa.Column('event_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('issue_id', sa.String(64), nullable=False),
        sa.Column('from_status', sa.String(16), nullable=True),
        sa.Column('to_status', sa.String(16), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('snapshot_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ('resolve', 'ignore', 'reopen')",
            name='ck_pipeline_quality_issue_event_action',
        ),
        sa.CheckConstraint(
            "to_status IN ('open', 'resolved', 'ignored')",
            name='ck_pipeline_quality_issue_event_to_status',
        ),
        sa.ForeignKeyConstraint(
            ['issue_id'],
            ['pipeline_quality_issues.issue_id'],
            ondelete='CASCADE',
            name='fk_pipeline_quality_issue_event_issue',
        ),
        sa.ForeignKeyConstraint(
            ['operator_id'],
            ['sys_user.user_id'],
            ondelete='SET NULL',
            name='fk_pipeline_quality_issue_event_operator',
        ),
    )
    op.create_index(
        'idx_pipeline_quality_issue_event_issue_time',
        'pipeline_quality_issue_events',
        ['issue_id', 'create_time'],
    )
    op.create_index(
        'idx_pipeline_quality_issue_event_operator_time',
        'pipeline_quality_issue_events',
        ['operator_id', 'create_time'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if 'pipeline_quality_issue_events' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_pipeline_quality_issue_event_operator_time', table_name='pipeline_quality_issue_events')
        op.drop_index('idx_pipeline_quality_issue_event_issue_time', table_name='pipeline_quality_issue_events')
        op.drop_table('pipeline_quality_issue_events')
        return
    if 'pipeline_quality_issue_events' in inspect(op.get_bind()).get_table_names():
        op.drop_index('idx_pipeline_quality_issue_event_operator_time', table_name='pipeline_quality_issue_events')
        op.drop_index('idx_pipeline_quality_issue_event_issue_time', table_name='pipeline_quality_issue_events')
        op.drop_table('pipeline_quality_issue_events')
