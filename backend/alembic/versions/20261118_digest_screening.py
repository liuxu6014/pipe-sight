"""Add separate article screening rules to digest templates."""

import sqlalchemy as sa
from alembic import op

revision = '20261118_digest_screening'
down_revision = '20261115_digest_schedule_user_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'templates',
        sa.Column(
            'screening_prompt',
            sa.Text(),
            nullable=True,
            comment='情报简报写作前的文章筛选提示词；为空时使用系统默认筛选规则',
        ),
    )


def downgrade() -> None:
    raise RuntimeError('Restore the verified backup; downgrade would discard saved screening rules.')
