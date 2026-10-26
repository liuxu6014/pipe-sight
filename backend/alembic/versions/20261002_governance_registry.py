"""Add persistent quality issue and duplicate group registries."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_governance_registry'
down_revision = '20261002_content_reprocess_audit'
branch_labels = None
depends_on = None


def _create_quality_issue_table() -> None:
    op.create_table(
        'pipeline_quality_issues',
        sa.Column('issue_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('content_type', sa.String(16), nullable=False),
        sa.Column('content_id', sa.String(64), nullable=False),
        sa.Column('issue_code', sa.String(32), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='warning'),
        sa.Column('evidence', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('suggestion', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', sa.String(16), nullable=False, server_default='open'),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.Column('update_time', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'content_type', 'content_id', 'issue_code', name='uk_pipeline_quality_issue_content_code'
        ),
        sa.CheckConstraint(
            "content_type IN ('article', 'paper')", name='ck_pipeline_quality_issue_content_type'
        ),
        sa.CheckConstraint(
            "issue_code IN ('duplicate', 'missing', 'tag', 'parse', 'review')",
            name='ck_pipeline_quality_issue_code',
        ),
        sa.CheckConstraint(
            "severity IN ('error', 'warning', 'info')", name='ck_pipeline_quality_issue_severity'
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'ignored')", name='ck_pipeline_quality_issue_status'
        ),
        sa.ForeignKeyConstraint(
            ['operator_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_quality_issue_operator'
        ),
    )
    op.create_index(
        'idx_pipeline_quality_issue_status_time',
        'pipeline_quality_issues',
        ['status', 'update_time'],
    )
    op.create_index(
        'idx_pipeline_quality_issue_content',
        'pipeline_quality_issues',
        ['content_type', 'content_id', 'status'],
    )


def _create_duplicate_tables() -> None:
    op.create_table(
        'pipeline_duplicate_groups',
        sa.Column('group_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('content_type', sa.String(16), nullable=False),
        sa.Column('group_key', sa.String(255), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='candidate'),
        sa.Column('master_content_id', sa.String(64), nullable=True),
        sa.Column('similarity', sa.Float(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.Column('update_time', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('content_type', 'group_key', name='uk_pipeline_duplicate_group_key'),
        sa.CheckConstraint(
            "content_type IN ('article', 'paper')", name='ck_pipeline_duplicate_group_content_type'
        ),
        sa.CheckConstraint(
            "status IN ('candidate', 'merged', 'split', 'dismissed')",
            name='ck_pipeline_duplicate_group_status',
        ),
        sa.CheckConstraint(
            'similarity IS NULL OR similarity BETWEEN 0 AND 1',
            name='ck_pipeline_duplicate_group_similarity',
        ),
        sa.ForeignKeyConstraint(
            ['operator_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_duplicate_group_operator'
        ),
    )
    op.create_index(
        'idx_pipeline_duplicate_group_status_time',
        'pipeline_duplicate_groups',
        ['status', 'update_time'],
    )
    op.create_table(
        'pipeline_duplicate_members',
        sa.Column('member_id', sa.BigInteger(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('group_id', sa.String(64), nullable=False),
        sa.Column('content_type', sa.String(16), nullable=False),
        sa.Column('content_id', sa.String(64), nullable=False),
        sa.Column('relation_type', sa.String(16), nullable=False, server_default='candidate'),
        sa.Column('similarity', sa.Float(), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            'group_id', 'content_type', 'content_id', name='uk_pipeline_duplicate_member_content'
        ),
        sa.CheckConstraint(
            "content_type IN ('article', 'paper')", name='ck_pipeline_duplicate_member_content_type'
        ),
        sa.CheckConstraint(
            "relation_type IN ('candidate', 'master', 'duplicate')",
            name='ck_pipeline_duplicate_member_relation_type',
        ),
        sa.CheckConstraint(
            'similarity IS NULL OR similarity BETWEEN 0 AND 1',
            name='ck_pipeline_duplicate_member_similarity',
        ),
        sa.ForeignKeyConstraint(
            ['group_id'], ['pipeline_duplicate_groups.group_id'], ondelete='CASCADE',
            name='fk_pipeline_duplicate_member_group',
        ),
    )
    op.create_index(
        'idx_pipeline_duplicate_member_content',
        'pipeline_duplicate_members',
        ['content_type', 'content_id'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _create_quality_issue_table()
        _create_duplicate_tables()
        return

    tables = set(inspect(op.get_bind()).get_table_names())
    if 'pipeline_quality_issues' not in tables:
        _create_quality_issue_table()
    if 'pipeline_duplicate_groups' not in tables:
        _create_duplicate_tables()


def downgrade() -> None:
    op.drop_index('idx_pipeline_duplicate_member_content', table_name='pipeline_duplicate_members')
    op.drop_table('pipeline_duplicate_members')
    op.drop_index('idx_pipeline_duplicate_group_status_time', table_name='pipeline_duplicate_groups')
    op.drop_table('pipeline_duplicate_groups')
    op.drop_index('idx_pipeline_quality_issue_content', table_name='pipeline_quality_issues')
    op.drop_index('idx_pipeline_quality_issue_status_time', table_name='pipeline_quality_issues')
    op.drop_table('pipeline_quality_issues')
