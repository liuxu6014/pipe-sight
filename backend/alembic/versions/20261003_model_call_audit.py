"""Add per-call model execution audit records without storing prompt bodies."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_model_call_audit'
down_revision = '20261003_quality_issue_audit'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'pipeline_model_call_audits',
        sa.Column('call_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('task_id', sa.String(64), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('scene', sa.String(32), nullable=False),
        sa.Column('route_id', sa.String(64), nullable=True),
        sa.Column('route_version_no', sa.Integer(), nullable=True),
        sa.Column('prompt_version_id', sa.String(64), nullable=True),
        sa.Column('template_version_id', sa.String(64), nullable=True),
        sa.Column('model_id', sa.BigInteger(), nullable=True),
        sa.Column('model_code', sa.String(100), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('attempt_no', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fallback_used', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('input_char_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_char_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('error_message', sa.String(1000), nullable=True),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'limit_exceeded')",
            name='ck_pipeline_model_call_audit_status',
        ),
        sa.CheckConstraint('attempt_no >= 0', name='ck_pipeline_model_call_audit_attempt'),
        sa.CheckConstraint(
            'latency_ms IS NULL OR latency_ms >= 0',
            name='ck_pipeline_model_call_audit_latency',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_model_call_audit_user'
        ),
        sa.ForeignKeyConstraint(
            ['route_id'],
            ['pipeline_model_routes.route_id'],
            ondelete='SET NULL',
            name='fk_pipeline_model_call_audit_route',
        ),
        sa.ForeignKeyConstraint(
            ['model_id'], ['ai_models.model_id'], ondelete='SET NULL', name='fk_pipeline_model_call_audit_model'
        ),
    )
    op.create_index(
        'idx_pipeline_model_call_audit_scene_time',
        'pipeline_model_call_audits',
        ['scene', 'create_time'],
    )
    op.create_index(
        'idx_pipeline_model_call_audit_status_time',
        'pipeline_model_call_audits',
        ['status', 'create_time'],
    )
    op.create_index(
        'idx_pipeline_model_call_audit_task_time',
        'pipeline_model_call_audits',
        ['task_id', 'create_time'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if 'pipeline_model_call_audits' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        for index_name in (
            'idx_pipeline_model_call_audit_task_time',
            'idx_pipeline_model_call_audit_status_time',
            'idx_pipeline_model_call_audit_scene_time',
        ):
            op.drop_index(index_name, table_name='pipeline_model_call_audits')
        op.drop_table('pipeline_model_call_audits')
        return
    if 'pipeline_model_call_audits' in inspect(op.get_bind()).get_table_names():
        for index_name in (
            'idx_pipeline_model_call_audit_task_time',
            'idx_pipeline_model_call_audit_status_time',
            'idx_pipeline_model_call_audit_scene_time',
        ):
            op.drop_index(index_name, table_name='pipeline_model_call_audits')
        op.drop_table('pipeline_model_call_audits')
