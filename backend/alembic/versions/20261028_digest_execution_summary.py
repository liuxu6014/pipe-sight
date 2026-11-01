"""Add nullable dispatch summary; never fabricate or backfill historical state."""

from typing import NoReturn

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = '20261028_digest_execution_summary'
down_revision = '20261025_beijing_audit_time'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if 'digest_schedules' not in inspector.get_table_names():
        return
    from app.schema_comments import COLUMN_COMMENTS  # noqa: PLC0415

    columns = {column['name'] for column in inspector.get_columns('digest_schedules')}
    additions = {
        'last_run_at': sa.Column('last_run_at', TIMESTAMP(precision=0, timezone=False), nullable=True),
        'last_status': sa.Column('last_status', sa.String(16), nullable=True),
        'last_error': sa.Column('last_error', sa.Text(), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column('digest_schedules', column)
            comment = COLUMN_COMMENTS['digest_schedules'][name].replace("'", "''")
            op.execute(f"COMMENT ON COLUMN public.digest_schedules.{name} IS '{comment}'")
    constraints = {item.get('name') for item in inspector.get_check_constraints('digest_schedules')}
    if 'ck_digest_schedules_last_status' in constraints:
        op.drop_constraint('ck_digest_schedules_last_status', 'digest_schedules', type_='check')
    op.create_check_constraint(
        'ck_digest_schedules_last_status',
        'digest_schedules',
        "last_status IS NULL OR last_status IN ('queued','no_data','skipped','failed')",
    )
    if 'generation_tasks' in inspector.get_table_names():
        task_columns = {column['name'] for column in inspector.get_columns('generation_tasks')}
        indexes = {item.get('name') for item in inspector.get_indexes('generation_tasks')}
        if {'schedule_id', 'id'} <= task_columns and 'idx_generation_tasks_schedule_id' not in indexes:
            op.create_index('idx_generation_tasks_schedule_id', 'generation_tasks', ['schedule_id', 'id'])


def downgrade() -> NoReturn:
    raise RuntimeError('Restore the verified backup; downgrading would discard execution summaries.')
