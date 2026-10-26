"""Repair historical handoff counters from durable article statuses."""

import sqlalchemy as sa
from alembic import context, op

revision = '20261002_handoff_status_repair'
down_revision = '20261002_handoff_rejection_count'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if not {'collection_runs', 'news_articles'}.issubset(tables):
        return
    columns = {item['name'] for item in inspector.get_columns('collection_runs')}
    if 'handoff_rejected_count' not in columns:
        return
    op.execute(
        sa.text(
            """
            UPDATE collection_runs AS runs
            SET handoff_count = GREATEST(runs.handoff_count, counts.terminal_count),
                handoff_rejected_count = counts.rejected_count,
                handoff_processed_count = counts.processed_count,
                handoff_failed_count = counts.failed_count,
                handoff_status = CASE
                    WHEN counts.terminal_count < GREATEST(runs.handoff_count, counts.terminal_count)
                        THEN 'processing'
                    WHEN counts.failed_count = 0 THEN 'completed'
                    WHEN counts.processed_count + counts.rejected_count > 0 THEN 'partial'
                    ELSE 'failed'
                END
            FROM (
                SELECT collection_run_id,
                       COUNT(*) FILTER (WHERE handoff_status = 'completed') AS processed_count,
                       COUNT(*) FILTER (WHERE handoff_status = 'rejected') AS rejected_count,
                       COUNT(*) FILTER (WHERE handoff_status = 'failed') AS failed_count,
                       COUNT(*) FILTER (WHERE handoff_status IN ('completed', 'rejected', 'failed')) AS terminal_count
                FROM news_articles
                WHERE collection_run_id IS NOT NULL
                GROUP BY collection_run_id
            ) AS counts
            WHERE runs.run_id = counts.collection_run_id
            """
        )
    )


def downgrade() -> None:
    # The repair only makes persisted counters agree with article statuses; it is
    # intentionally not reversed because the previous values were semantically wrong.
    return
