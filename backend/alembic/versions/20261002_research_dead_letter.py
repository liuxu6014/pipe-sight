"""Add an explicit dead-letter state for exhausted research jobs."""

from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_research_dead_letter'
down_revision = '20261002_research_cancel_requests'
branch_labels = None
depends_on = None

_STATUS_CONSTRAINT = 'ck_generation_tasks_status'
_STATUS_SQL = "status IN ('queued', 'running', 'completed', 'failed', 'dead_letter', 'cancelled')"


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(_STATUS_CONSTRAINT, 'generation_tasks', type_='check')
        op.create_check_constraint(_STATUS_CONSTRAINT, 'generation_tasks', _STATUS_SQL)
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    constraints = {item['name'] for item in inspector.get_check_constraints('generation_tasks')}
    if _STATUS_CONSTRAINT in constraints:
        op.drop_constraint(_STATUS_CONSTRAINT, 'generation_tasks', type_='check')
    op.create_check_constraint(_STATUS_CONSTRAINT, 'generation_tasks', _STATUS_SQL)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint(_STATUS_CONSTRAINT, 'generation_tasks', type_='check')
        op.create_check_constraint(
            _STATUS_CONSTRAINT,
            'generation_tasks',
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'generation_tasks' not in inspector.get_table_names():
        return
    op.execute("UPDATE generation_tasks SET status = 'failed' WHERE status = 'dead_letter'")
    constraints = {item['name'] for item in inspector.get_check_constraints('generation_tasks')}
    if _STATUS_CONSTRAINT in constraints:
        op.drop_constraint(_STATUS_CONSTRAINT, 'generation_tasks', type_='check')
    op.create_check_constraint(
        _STATUS_CONSTRAINT,
        'generation_tasks',
        "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
    )
