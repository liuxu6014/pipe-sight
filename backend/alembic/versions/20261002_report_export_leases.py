"""Add durable lease and retry state to report export jobs."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_report_export_leases'
down_revision = '20261002_report_exports'
branch_labels = None
depends_on = None


def _columns(bind: sa.engine.Connection) -> set[str]:
    return {item['name'] for item in inspect(bind).get_columns('report_exports')}


def _add_columns() -> None:
    op.add_column(
        'report_exports',
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0', comment='执行尝试次数'),
    )
    op.add_column('report_exports', sa.Column('lease_owner', sa.String(128), nullable=True, comment='当前执行器租约持有者'))
    op.add_column('report_exports', sa.Column('lease_until', sa.DateTime(), nullable=True, comment='当前执行器租约到期时间'))
    op.add_column('report_exports', sa.Column('next_retry_at', sa.DateTime(), nullable=True, comment='下次重试时间'))


def _add_constraints_and_index() -> None:
    op.create_check_constraint(
        'ck_report_exports_attempt_count',
        'report_exports',
        'attempt_count >= 0',
    )
    op.create_index(
        'idx_report_exports_dispatch',
        'report_exports',
        ['status', 'next_retry_at', 'lease_until', 'update_time'],
    )


def upgrade() -> None:
    if context.is_offline_mode():
        _add_columns()
        _add_constraints_and_index()
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'report_exports' not in inspector.get_table_names():
        return
    columns = _columns(bind)
    if 'attempt_count' not in columns:
        _add_columns()
    # 旧版本没有租约字段；将未完成的旧运行态任务重新放回可领取队列。
    op.execute(
        "UPDATE report_exports SET status = 'queued', lease_owner = NULL, lease_until = NULL "
        "WHERE status = 'running' AND lease_until IS NULL"
    )
    constraints = {item['name'] for item in inspect(bind).get_check_constraints('report_exports')}
    indexes = {item['name'] for item in inspect(bind).get_indexes('report_exports')}
    if 'ck_report_exports_attempt_count' not in constraints:
        op.create_check_constraint('ck_report_exports_attempt_count', 'report_exports', 'attempt_count >= 0')
    if 'idx_report_exports_dispatch' not in indexes:
        op.create_index(
            'idx_report_exports_dispatch',
            'report_exports',
            ['status', 'next_retry_at', 'lease_until', 'update_time'],
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_report_exports_dispatch', table_name='report_exports')
        op.drop_constraint('ck_report_exports_attempt_count', 'report_exports', type_='check')
        for column_name in ('next_retry_at', 'lease_until', 'lease_owner', 'attempt_count'):
            op.drop_column('report_exports', column_name)
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'report_exports' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspect(bind).get_indexes('report_exports')}
    if 'idx_report_exports_dispatch' in indexes:
        op.drop_index('idx_report_exports_dispatch', table_name='report_exports')
    constraints = {item['name'] for item in inspect(bind).get_check_constraints('report_exports')}
    if 'ck_report_exports_attempt_count' in constraints:
        op.drop_constraint('ck_report_exports_attempt_count', 'report_exports', type_='check')
    columns = _columns(bind)
    for column_name in ('next_retry_at', 'lease_until', 'lease_owner', 'attempt_count'):
        if column_name in columns:
            op.drop_column('report_exports', column_name)
