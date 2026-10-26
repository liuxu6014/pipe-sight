"""Add atomic daily usage counters for model routes."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_model_route_usage'
down_revision = '20261002_model_routes'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'pipeline_model_route_usage',
        sa.Column('route_id', sa.String(64), nullable=False),
        sa.Column('usage_date', sa.DateTime(), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('create_time', sa.DateTime(), nullable=False),
        sa.Column('update_time', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('route_id', 'usage_date', name='pk_pipeline_model_route_usage'),
        sa.CheckConstraint('call_count >= 0', name='ck_pipeline_model_route_usage_count'),
        sa.ForeignKeyConstraint(
            ['route_id'], ['pipeline_model_routes.route_id'], ondelete='CASCADE',
            name='fk_pipeline_model_route_usage_route',
        ),
    )
    op.create_index('idx_pipeline_model_route_usage_date', 'pipeline_model_route_usage', ['usage_date'])


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if 'pipeline_model_route_usage' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_pipeline_model_route_usage_date', table_name='pipeline_model_route_usage')
        op.drop_table('pipeline_model_route_usage')
        return
    if 'pipeline_model_route_usage' in inspect(op.get_bind()).get_table_names():
        op.drop_index('idx_pipeline_model_route_usage_date', table_name='pipeline_model_route_usage')
        op.drop_table('pipeline_model_route_usage')
