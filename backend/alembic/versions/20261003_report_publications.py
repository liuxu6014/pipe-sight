"""Add immutable report publication audit records."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_report_publications'
down_revision = '20261003_digest_schedules'
branch_labels = None
depends_on = None

TABLE_NAME = 'report_publications'


def _create_table() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column('publication_id', sa.String(64), nullable=False, comment='发布记录ID'),
        sa.Column('report_id', sa.String(64), nullable=False, comment='报告ID'),
        sa.Column('report_version_no', sa.Integer(), nullable=False, comment='发布时的报告版本号'),
        sa.Column('action', sa.String(16), nullable=False, comment='publish或unpublish'),
        sa.Column('operator_id', sa.BigInteger(), nullable=True, comment='操作用户ID'),
        sa.Column('operator_name', sa.String(64), nullable=False, comment='操作用户名称快照'),
        sa.Column('note', sa.Text(), nullable=True, comment='发布或撤销说明'),
        sa.Column('create_time', sa.DateTime(), nullable=False, comment='操作时间'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.report_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['operator_id'], ['sys_user.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('publication_id'),
        sa.CheckConstraint("action IN ('publish', 'unpublish')", name='ck_report_publications_action'),
        sa.CheckConstraint('report_version_no >= 1', name='ck_report_publications_report_version_no'),
        comment='报告正式发布与撤销发布审计记录表',
    )
    op.create_index('idx_report_publications_report_time', TABLE_NAME, ['report_id', 'create_time'])
    op.create_index('idx_report_publications_action_time', TABLE_NAME, ['action', 'create_time'])


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if TABLE_NAME not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index('idx_report_publications_action_time', table_name=TABLE_NAME)
        op.drop_index('idx_report_publications_report_time', table_name=TABLE_NAME)
        op.drop_table(TABLE_NAME)
        return
    if TABLE_NAME not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index('idx_report_publications_action_time', table_name=TABLE_NAME)
    op.drop_index('idx_report_publications_report_time', table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
