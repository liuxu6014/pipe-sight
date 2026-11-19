"""Store per-category screening rules without rewriting existing templates."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20261118_digest_categories'
down_revision = '20261118_digest_screening'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'templates',
        sa.Column(
            'screening_categories',
            postgresql.JSONB(),
            nullable=True,
            comment='简报筛选类别及逐类提示词的JSON数组；空数组表示自由分类，NULL兼容历史模板',
        ),
    )
    op.create_check_constraint(
        'ck_templates_screening_categories',
        'templates',
        "screening_categories IS NULL OR (purpose='digest' AND jsonb_typeof(screening_categories)='array')",
    )


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; downgrade would discard saved category rules.')
