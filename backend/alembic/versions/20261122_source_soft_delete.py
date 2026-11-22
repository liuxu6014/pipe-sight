"""Source soft-delete flag; preserve collection records and news."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op

revision = '20261122_source_soft_delete'
down_revision = '20261120_material_comments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comments = COLUMN_COMMENTS['data_sources']
    op.add_column(
        'data_sources',
        sa.Column(
            'is_deleted',
            sa.Boolean,
            nullable=False,
            server_default=sa.text('false'),
            comment=comments['is_deleted'],
        ),
    )


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; dropping this flag would lose soft-deleted source state.')
