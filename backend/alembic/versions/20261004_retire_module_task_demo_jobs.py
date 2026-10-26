"""Retire the legacy module_task scheduler demo jobs."""

import sqlalchemy as sa
from alembic import op

revision = '20261004_retire_module_task_demo_jobs'
down_revision = '20261003_model_call_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Disable only the obsolete bundled demo targets; keep user-created jobs."""
    op.execute(
        sa.text(
            """
            UPDATE sys_job
            SET status = '1', update_time = CURRENT_TIMESTAMP
            WHERE invoke_target LIKE 'module_task.scheduler_test.%'
            """
        )
    )


def downgrade() -> None:
    """Do not reactivate removed demo jobs during downgrade."""
