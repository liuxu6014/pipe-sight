"""Compatibility cleanup for an intermediate development schema.

Only ``crawl_tasks`` had the same columns as the final ``collection_runs``
table.  Older ``contents``/``articles``/``papers`` shapes are intentionally
not renamed because doing so would silently make the ORM read the wrong
columns; those tables remain available for explicit, reviewed data migration.
"""

from alembic import context, op
from sqlalchemy import inspect

revision = '20260814_simplify_domain'
down_revision = '20260814_pipeline_domain'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    existing = set(inspect(connection).get_table_names())
    if 'crawl_tasks' in existing and 'collection_runs' not in existing:
        op.rename_table('crawl_tasks', 'collection_runs')


def downgrade() -> None:
    # Compatibility revision never drops or rewrites data.
    return None
