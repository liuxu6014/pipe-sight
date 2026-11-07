"""Bind concrete research templates to a report type without guessing from names."""

import sqlalchemy as sa
from alembic import op

revision = '20261107_template_report_type'
down_revision = '20261107_content_processing'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'templates',
        sa.Column(
            'report_type',
            sa.String(32),
            nullable=True,
            comment='科研报告类型：research-demand、technology-route、project-demand；旧模板未绑定时为空，不从名称推断',
        ),
    )
    op.create_check_constraint(
        'ck_templates_report_type',
        'templates',
        "report_type IS NULL OR (purpose = 'research' AND report_type IN ('research-demand','technology-route','project-demand'))",
    )


def downgrade() -> None:
    raise RuntimeError('此迁移保留报告类型绑定；回退请使用迁移前备份，不自动删除配置。')
