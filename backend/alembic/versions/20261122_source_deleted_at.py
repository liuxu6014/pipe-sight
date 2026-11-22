"""Unify source soft-delete on deleted_at; drop the temporary is_deleted flag."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = '20261122_source_deleted_at'
down_revision = '20261122_source_soft_delete'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comments = COLUMN_COMMENTS['data_sources']
    op.drop_column('data_sources', 'is_deleted')
    op.add_column(
        'data_sources',
        sa.Column('deleted_at', TIMESTAMP(precision=0), nullable=True, comment=comments['deleted_at']),
    )


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; dropping deleted_at would lose soft-deleted source state.')
