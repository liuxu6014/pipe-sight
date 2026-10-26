"""Separate business rejection from external processing failure."""

from typing import Any

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_handoff_rejection_count'
down_revision = '20261002_research_job_idempotency'
branch_labels = None
depends_on = None

_COUNTER_CHECK = (
    'fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 '
    'AND duplicate_count >= 0 AND failed_count >= 0 AND handoff_count >= 0 '
    'AND handoff_processed_count >= 0 AND handoff_rejected_count >= 0 '
    'AND handoff_failed_count >= 0'
)


def _replace_counter_checks(bind_inspector: Any) -> None:
    existing = {
        item['name']
        for item in bind_inspector.get_check_constraints('collection_runs')
        if item.get('name') in {'ck_collection_runs_counters', 'ck_collection_runs_handoff_counters'}
    }
    for name in existing:
        op.drop_constraint(name, 'collection_runs', type_='check')
    op.create_check_constraint('ck_collection_runs_counters', 'collection_runs', _COUNTER_CHECK)


def _repair_existing_run_counts() -> None:
    # Existing versions counted InsightHub business rejections as failures. Rebuild
    # the counters from the durable article status before serving the new contract.
    op.execute(
        sa.text(
            """
            UPDATE collection_runs AS runs
            SET handoff_rejected_count = counts.rejected_count,
                handoff_processed_count = counts.processed_count,
                handoff_failed_count = counts.failed_count,
                handoff_status = CASE
                    WHEN counts.terminal_count < runs.handoff_count THEN 'processing'
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
              AND runs.handoff_count > 0
            """
        )
    )


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(
            'collection_runs',
            sa.Column('handoff_rejected_count', sa.Integer(), nullable=False, server_default='0'),
        )
        op.drop_constraint('ck_collection_runs_counters', 'collection_runs', type_='check')
        op.create_check_constraint('ck_collection_runs_counters', 'collection_runs', _COUNTER_CHECK)
        return

    inspector = inspect(op.get_bind())
    if 'collection_runs' not in inspector.get_table_names():
        return
    columns = {item['name'] for item in inspector.get_columns('collection_runs')}
    if 'handoff_rejected_count' not in columns:
        op.add_column(
            'collection_runs',
            sa.Column('handoff_rejected_count', sa.Integer(), nullable=False, server_default='0'),
        )
    _replace_counter_checks(inspect(op.get_bind()))
    if 'news_articles' in inspect(op.get_bind()).get_table_names():
        _repair_existing_run_counts()


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint('ck_collection_runs_counters', 'collection_runs', type_='check')
        op.create_check_constraint(
            'ck_collection_runs_counters',
            'collection_runs',
            'fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 '
            'AND duplicate_count >= 0 AND failed_count >= 0 AND handoff_count >= 0 '
            'AND handoff_processed_count >= 0 AND handoff_failed_count >= 0',
        )
        op.drop_column('collection_runs', 'handoff_rejected_count')
        return

    inspector = inspect(op.get_bind())
    if 'collection_runs' not in inspector.get_table_names():
        return
    checks = {
        item['name']
        for item in inspector.get_check_constraints('collection_runs')
        if item.get('name') == 'ck_collection_runs_counters'
    }
    if checks:
        op.drop_constraint('ck_collection_runs_counters', 'collection_runs', type_='check')
    op.create_check_constraint(
        'ck_collection_runs_counters',
        'collection_runs',
        'fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 '
        'AND duplicate_count >= 0 AND failed_count >= 0 AND handoff_count >= 0 '
        'AND handoff_processed_count >= 0 AND handoff_failed_count >= 0',
    )
    columns = {item['name'] for item in inspect(op.get_bind()).get_columns('collection_runs')}
    if 'handoff_rejected_count' in columns:
        op.drop_column('collection_runs', 'handoff_rejected_count')
