"""Persist cooperative cancellation requests for research jobs."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_research_cancel_requests'
down_revision = '20261002_research_job_leases'
branch_labels = None
depends_on = None


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {item['name'] for item in inspect(bind).get_columns('generation_tasks')}


def _add_column() -> None:
    op.add_column(
        'generation_tasks',
        sa.Column('cancel_requested_at', sa.DateTime(), nullable=True, comment='用户请求取消时间'),
    )


def _add_index() -> None:
    op.create_index(
        'idx_generation_tasks_cancel_dispatch',
        'generation_tasks',
        ['status', 'cancel_requested_at', 'lease_until', 'update_time'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _add_column()
        _add_index()
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    if 'cancel_requested_at' not in _columns(bind):
        _add_column()
    indexes = {item['name'] for item in inspect(bind).get_indexes('generation_tasks')}
    if 'idx_generation_tasks_cancel_dispatch' not in indexes:
        _add_index()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_generation_tasks_cancel_dispatch', table_name='generation_tasks')
        op.drop_column('generation_tasks', 'cancel_requested_at')
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspect(bind).get_indexes('generation_tasks')}
    if 'idx_generation_tasks_cancel_dispatch' in indexes:
        op.drop_index('idx_generation_tasks_cancel_dispatch', table_name='generation_tasks')
    if 'cancel_requested_at' in _columns(bind):
        op.drop_column('generation_tasks', 'cancel_requested_at')
