"""Persist paper core entities; use the same semantic contract for news."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261102_core_content_entities'
down_revision = '20261102_news_summary'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    columns = {column['name'] for column in inspect(op.get_bind()).get_columns('papers')}
    if 'entities' not in columns:
        op.add_column('papers', sa.Column('entities', JSONB(), nullable=True))
    for table in ('papers', 'news_articles'):
        comment = COLUMN_COMMENTS[table]['entities'].replace("'", "''")
        op.execute(f"COMMENT ON COLUMN {table}.entities IS '{comment}'")


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard saved paper entities.')
