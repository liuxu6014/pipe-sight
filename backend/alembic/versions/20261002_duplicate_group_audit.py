"""Add immutable duplicate-group governance events."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_duplicate_group_audit'
down_revision = '20261002_governance_permission_button'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'pipeline_duplicate_group_events',
        sa.Column('event_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('group_id', sa.String(64), nullable=False),
        sa.Column('from_status', sa.String(16), nullable=True),
        sa.Column('to_status', sa.String(16), nullable=False),
        sa.Column('action', sa.String(16), nullable=False),
        sa.Column('master_content_id', sa.String(64), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('snapshot_json', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "action IN ('merge', 'split', 'dismiss', 'reopen')",
            name='ck_pipeline_duplicate_event_action',
        ),
        sa.CheckConstraint(
            "to_status IN ('candidate', 'merged', 'split', 'dismissed')",
            name='ck_pipeline_duplicate_event_to_status',
        ),
        sa.ForeignKeyConstraint(
            ['group_id'],
            ['pipeline_duplicate_groups.group_id'],
            ondelete='CASCADE',
            name='fk_pipeline_duplicate_event_group',
        ),
        sa.ForeignKeyConstraint(
            ['operator_id'],
            ['sys_user.user_id'],
            ondelete='SET NULL',
            name='fk_pipeline_duplicate_event_operator',
        ),
    )
    op.create_index(
        'idx_pipeline_duplicate_event_group_time',
        'pipeline_duplicate_group_events',
        ['group_id', 'create_time'],
    )
    op.create_index(
        'idx_pipeline_duplicate_event_operator_time',
        'pipeline_duplicate_group_events',
        ['operator_id', 'create_time'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return

    if 'pipeline_duplicate_group_events' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_pipeline_duplicate_event_operator_time', table_name='pipeline_duplicate_group_events')
        op.drop_index('idx_pipeline_duplicate_event_group_time', table_name='pipeline_duplicate_group_events')
        op.drop_table('pipeline_duplicate_group_events')
        return

    tables = set(inspect(op.get_bind()).get_table_names())
    if 'pipeline_duplicate_group_events' in tables:
        op.drop_index('idx_pipeline_duplicate_event_operator_time', table_name='pipeline_duplicate_group_events')
        op.drop_index('idx_pipeline_duplicate_event_group_time', table_name='pipeline_duplicate_group_events')
        op.drop_table('pipeline_duplicate_group_events')
