"""Persist generated paper summaries separately from the original abstract."""

from alembic import op
from sqlalchemy import Column, Text, inspect

revision = '20261107_content_processing'
down_revision = '20261106_digest_result_stats'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if 'papers' in inspector.get_table_names() and 'summary' not in {
        column['name'] for column in inspector.get_columns('papers')
    }:
        op.add_column(
            'papers', Column('summary', Text(), nullable=True, comment='采集处理时生成的中文概述；与原文及译文摘要分别保存，不声称阅读全文')
        )


def downgrade() -> None:
    raise RuntimeError('此迁移保留已生成摘要；请通过备份恢复，不自动删除内容字段。')
