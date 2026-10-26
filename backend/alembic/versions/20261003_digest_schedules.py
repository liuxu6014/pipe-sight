"""Add durable schedules for daily, weekly and monthly intelligence digests."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_digest_schedules'
down_revision = '20261003_collection_active_source_guard'
branch_labels = None
depends_on = None

TABLE_NAME = 'digest_schedules'


def _create_table() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column('schedule_id', sa.String(64), nullable=False, comment='计划ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='创建用户ID'),
        sa.Column('owner_name', sa.String(64), nullable=False, comment='创建用户名称快照'),
        sa.Column('name', sa.String(255), nullable=False, comment='计划名称'),
        sa.Column('report_type', sa.String(32), nullable=False, comment='日报、周报或月报'),
        sa.Column('template_id', sa.String(64), nullable=False, comment='已发布模板编码'),
        sa.Column('template_version', sa.String(32), nullable=True, comment='模板版本快照'),
        sa.Column('schedule_time', sa.String(5), nullable=False, server_default='08:00', comment='本地执行时间HH:MM'),
        sa.Column('config', sa.JSON(), nullable=False, comment='生成筛选和内容配置快照'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true(), comment='是否启用'),
        sa.Column('next_run_time', sa.DateTime(), nullable=False, comment='下次执行时间'),
        sa.Column('last_run_time', sa.DateTime(), nullable=True, comment='最近一次调度时间'),
        sa.Column('last_task_id', sa.String(64), nullable=True, comment='最近生成任务ID'),
        sa.Column('last_status', sa.String(32), nullable=True, comment='最近一次调度状态'),
        sa.Column('last_error', sa.Text(), nullable=True, comment='最近一次失败说明'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0', comment='连续失败次数'),
        sa.Column('lease_owner', sa.String(128), nullable=True, comment='调度执行器租约持有者'),
        sa.Column('lease_until', sa.DateTime(), nullable=True, comment='调度执行器租约到期时间'),
        sa.Column('create_time', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_task_id'], ['generation_tasks.task_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('schedule_id'),
        sa.CheckConstraint("report_type IN ('daily', 'weekly', 'monthly')", name='ck_digest_schedules_report_type'),
        sa.CheckConstraint(
            "last_status IS NULL OR last_status IN ('queued', 'no_data', 'failed')",
            name='ck_digest_schedules_last_status',
        ),
        sa.CheckConstraint('failure_count >= 0', name='ck_digest_schedules_failure_count'),
        comment='周期情报简报自动生成计划表',
    )
    op.create_index(
        'idx_digest_schedules_dispatch',
        TABLE_NAME,
        ['enabled', 'next_run_time', 'lease_until'],
    )
    op.create_index('idx_digest_schedules_user_time', TABLE_NAME, ['user_id', 'update_time'])


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if TABLE_NAME not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_digest_schedules_user_time', table_name=TABLE_NAME)
        op.drop_index('idx_digest_schedules_dispatch', table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)
        return
    if TABLE_NAME not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index('idx_digest_schedules_user_time', table_name=TABLE_NAME)
    op.drop_index('idx_digest_schedules_dispatch', table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
