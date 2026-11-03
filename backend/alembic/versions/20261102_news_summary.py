"""Persist generated news summaries independently of original content."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '20261102_news_summary'
down_revision = '20261102_news_articles_entities'
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column['name'] for column in inspect(op.get_bind()).get_columns('news_articles')}
    if 'summary' not in columns:
        op.add_column('news_articles', sa.Column('summary', sa.Text(), nullable=True))
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comment = COLUMN_COMMENTS['news_articles']['summary'].replace("'", "''")
    op.execute(f"COMMENT ON COLUMN news_articles.summary IS '{comment}'")


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard saved summaries.')
