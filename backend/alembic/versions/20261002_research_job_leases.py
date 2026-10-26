"""Add durable lease and retry state to research generation jobs."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_research_job_leases'
down_revision = '20261002_report_export_leases'
branch_labels = None
depends_on = None


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {item['name'] for item in inspect(bind).get_columns('generation_tasks')}


def _add_columns() -> None:
    op.add_column(
        'generation_tasks',
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0', comment='执行尝试次数'),
    )
    op.add_column('generation_tasks', sa.Column('lease_owner', sa.String(128), nullable=True, comment='当前执行器租约持有者'))
    op.add_column('generation_tasks', sa.Column('lease_until', sa.DateTime(), nullable=True, comment='当前执行器租约到期时间'))
    op.add_column('generation_tasks', sa.Column('next_retry_at', sa.DateTime(), nullable=True, comment='下次重试时间'))


def upgrade() -> None:
    if context.is_offline_mode():
        _add_columns()
        op.create_check_constraint('ck_generation_tasks_attempt_count', 'generation_tasks', 'attempt_count >= 0')
        op.create_index(
            'idx_generation_tasks_dispatch',
            'generation_tasks',
            ['status', 'next_retry_at', 'lease_until', 'update_time'],
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    if 'attempt_count' not in _columns(bind):
        _add_columns()
    # 旧版本没有租约字段；未完成的旧运行态任务必须回到可领取队列。
    op.execute(
        "UPDATE generation_tasks SET status = 'queued', lease_owner = NULL, lease_until = NULL "
        "WHERE status = 'running' AND lease_until IS NULL"
    )
    constraints = {item['name'] for item in inspect(bind).get_check_constraints('generation_tasks')}
    if 'ck_generation_tasks_attempt_count' not in constraints:
        op.create_check_constraint('ck_generation_tasks_attempt_count', 'generation_tasks', 'attempt_count >= 0')
    indexes = {item['name'] for item in inspect(bind).get_indexes('generation_tasks')}
    if 'idx_generation_tasks_dispatch' not in indexes:
        op.create_index(
            'idx_generation_tasks_dispatch',
            'generation_tasks',
            ['status', 'next_retry_at', 'lease_until', 'update_time'],
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_generation_tasks_dispatch', table_name='generation_tasks')
        op.drop_constraint('ck_generation_tasks_attempt_count', 'generation_tasks', type_='check')
        for column_name in ('next_retry_at', 'lease_until', 'lease_owner', 'attempt_count'):
            op.drop_column('generation_tasks', column_name)
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspect(bind).get_indexes('generation_tasks')}
    if 'idx_generation_tasks_dispatch' in indexes:
        op.drop_index('idx_generation_tasks_dispatch', table_name='generation_tasks')
    constraints = {item['name'] for item in inspect(bind).get_check_constraints('generation_tasks')}
    if 'ck_generation_tasks_attempt_count' in constraints:
        op.drop_constraint('ck_generation_tasks_attempt_count', 'generation_tasks', type_='check')
    columns = _columns(bind)
    for column_name in ('next_retry_at', 'lease_until', 'lease_owner', 'attempt_count'):
        if column_name in columns:
            op.drop_column('generation_tasks', column_name)
