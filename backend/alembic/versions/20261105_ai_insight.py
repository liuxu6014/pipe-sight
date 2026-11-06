"""Add ai_insight JSON columns for pipeline-network insight and paper AI interpretation."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261105_ai_insight'
down_revision = '20261103_restore_departments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    inspector = inspect(op.get_bind())
    for table in ('news_articles', 'papers'):
        if table not in inspector.get_table_names():
            continue
        columns = {column['name'] for column in inspector.get_columns(table)}
        if 'ai_insight' not in columns:
            op.add_column(table, sa.Column('ai_insight', JSONB(), nullable=True))
        comment = COLUMN_COMMENTS[table]['ai_insight'].replace("'", "''")
        op.execute(f"COMMENT ON COLUMN public.{table}.ai_insight IS '{comment}'")


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard saved AI insights.')
