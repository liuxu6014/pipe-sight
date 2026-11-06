"""Persist cumulative outcomes for automatic digest schedules."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op

revision = '20261106_digest_result_stats'
down_revision = '20261105_ai_insight'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    comments = COLUMN_COMMENTS['digest_schedules']
    for name in ('success_count', 'failure_count', 'skipped_count'):
        op.add_column(
            'digest_schedules', sa.Column(name, sa.BigInteger(), nullable=False, server_default='0', comment=comments[name])
        )
    op.add_column(
        'digest_schedules',
        sa.Column('last_failed_due_at', sa.DateTime(timezone=True), comment=comments['last_failed_due_at']),
    )
    op.execute("""
        UPDATE digest_schedules
        SET failure_count = CASE WHEN last_status = 'failed' THEN 1 ELSE 0 END,
            skipped_count = CASE WHEN last_status IN ('no_data', 'skipped') THEN 1 ELSE 0 END,
            last_failed_due_at = CASE
                WHEN last_status = 'failed' AND next_run_at <= (last_run_at AT TIME ZONE 'Asia/Shanghai')
                THEN next_run_at
            END
        WHERE last_status IN ('failed', 'no_data', 'skipped')
    """)
    op.execute("""
        UPDATE digest_schedules AS schedule
        SET success_count = history.success_count,
            failure_count = schedule.failure_count + history.failure_count
        FROM (
            SELECT task.schedule_id,
                   count(*) FILTER (WHERE task.status = 'completed') AS success_count,
                   count(*) FILTER (WHERE task.status = 'failed') AS failure_count
            FROM generation_tasks AS task
            JOIN reports AS report ON report.id = task.report_id
            JOIN digest_schedules AS owner ON owner.id = task.schedule_id AND owner.user_id = report.user_id
            WHERE task.status IN ('completed', 'failed')
            GROUP BY task.schedule_id
        ) AS history
        WHERE schedule.id = history.schedule_id
    """)


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard cumulative digest results.')
