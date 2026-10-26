"""Add persistent pipeline model routes."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_model_routes'
down_revision = '20261002_duplicate_group_audit'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'pipeline_model_routes',
        sa.Column('route_id', sa.String(64), primary_key=True, nullable=False),
        sa.Column('scene', sa.String(32), nullable=False),
        sa.Column('primary_model_id', sa.BigInteger(), nullable=True),
        sa.Column('fallback_model_id', sa.BigInteger(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='2048'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.2'),
        sa.Column('daily_limit', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('version_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('operator_id', sa.BigInteger(), nullable=True),
        sa.Column('operator_name', sa.String(64), nullable=False, server_default=''),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.Column('update_time', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('scene', name='uk_pipeline_model_routes_scene'),
        sa.CheckConstraint("scene IN ('research', 'digest', 'data-filter')", name='ck_pipeline_model_routes_scene'),
        sa.CheckConstraint('timeout_seconds BETWEEN 1 AND 120', name='ck_pipeline_model_routes_timeout'),
        sa.CheckConstraint('max_tokens BETWEEN 1 AND 32768', name='ck_pipeline_model_routes_max_tokens'),
        sa.CheckConstraint('temperature BETWEEN 0 AND 2', name='ck_pipeline_model_routes_temperature'),
        sa.CheckConstraint('daily_limit >= 0', name='ck_pipeline_model_routes_daily_limit'),
        sa.CheckConstraint('version_no >= 1', name='ck_pipeline_model_routes_version'),
        sa.ForeignKeyConstraint(['primary_model_id'], ['ai_models.model_id'], ondelete='RESTRICT', name='fk_pipeline_route_primary_model'),
        sa.ForeignKeyConstraint(['fallback_model_id'], ['ai_models.model_id'], ondelete='RESTRICT', name='fk_pipeline_route_fallback_model'),
        sa.ForeignKeyConstraint(['operator_id'], ['sys_user.user_id'], ondelete='SET NULL', name='fk_pipeline_route_operator'),
    )
    op.create_index('idx_pipeline_model_routes_enabled', 'pipeline_model_routes', ['enabled', 'scene'])


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if 'pipeline_model_routes' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_pipeline_model_routes_enabled', table_name='pipeline_model_routes')
        op.drop_table('pipeline_model_routes')
        return
    if 'pipeline_model_routes' in inspect(op.get_bind()).get_table_names():
        op.drop_index('idx_pipeline_model_routes_enabled', table_name='pipeline_model_routes')
        op.drop_table('pipeline_model_routes')
