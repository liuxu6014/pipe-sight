"""Persist report export jobs and generated file metadata."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_report_exports'
down_revision = '20261002_material_scan_state'
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        'report_exports',
        sa.Column('export_id', sa.String(64), nullable=False, comment='导出任务ID'),
        sa.Column('report_id', sa.String(64), nullable=False, comment='报告ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='导出用户ID'),
        sa.Column('report_version_no', sa.Integer(), nullable=False, comment='报告版本号快照'),
        sa.Column('report_revision', sa.DateTime(), nullable=False, comment='报告修订时间快照'),
        sa.Column('format', sa.String(16), nullable=False, comment='导出格式'),
        sa.Column('template_version', sa.String(64), nullable=True, comment='模板版本快照'),
        sa.Column('file_name', sa.String(500), nullable=False, comment='导出文件名'),
        sa.Column('file_key', sa.String(500), nullable=False, comment='受控存储键'),
        sa.Column('content_type', sa.String(128), nullable=False, comment='文件媒体类型'),
        sa.Column('file_size', sa.BigInteger(), server_default='0', nullable=False, comment='文件大小'),
        sa.Column('file_hash', sa.String(128), nullable=True, comment='文件SHA-256'),
        sa.Column('snapshot', sa.JSON(), nullable=False, comment='报告导出内容快照'),
        sa.Column('status', sa.String(32), server_default='queued', nullable=False, comment='导出状态'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='失败说明'),
        sa.Column('create_time', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('update_time', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('completed_time', sa.DateTime(), nullable=True, comment='完成时间'),
        sa.CheckConstraint("format IN ('docx', 'pdf')", name='ck_report_exports_format'),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name='ck_report_exports_status',
        ),
        sa.CheckConstraint('report_version_no >= 1', name='ck_report_exports_report_version_no'),
        sa.CheckConstraint('file_size >= 0', name='ck_report_exports_file_size'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.report_id'], name='fk_report_exports_report', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.user_id'], name='fk_report_exports_user', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('export_id'),
        comment='报告导出任务和文件审计表',
    )
    op.create_index(
        'idx_report_exports_user_report_time',
        'report_exports',
        ['user_id', 'report_id', 'create_time'],
    )
    op.create_index('idx_report_exports_status_time', 'report_exports', ['status', 'update_time'])


def upgrade() -> None:
    if context.is_offline_mode():
        _create_table()
        return
    if 'report_exports' not in inspect(op.get_bind()).get_table_names():
        _create_table()


def downgrade() -> None:
    if context.is_offline_mode() or 'report_exports' in inspect(op.get_bind()).get_table_names():
        op.drop_table('report_exports')
