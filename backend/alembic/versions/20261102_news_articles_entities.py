"""Add nullable news_articles.entities JSON column for entity extraction."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261102_news_articles_entities'
down_revision = '20261028_digest_execution_summary'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if 'news_articles' not in inspector.get_table_names():
        return
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    columns = {column['name'] for column in inspector.get_columns('news_articles')}
    if 'entities' not in columns:
        op.add_column('news_articles', sa.Column('entities', JSONB(), nullable=True))
    comment = COLUMN_COMMENTS['news_articles']['entities'].replace("'", "''")
    op.execute(f"COMMENT ON COLUMN public.news_articles.entities IS '{comment}'")


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard extracted entities.')
