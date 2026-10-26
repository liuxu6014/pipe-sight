"""Add client request idempotency for research generation jobs."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261002_research_job_idempotency'
down_revision = '20261002_model_route_usage'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column('generation_tasks', sa.Column('request_id', sa.String(128), nullable=True))
        op.create_unique_constraint(
            'uk_generation_tasks_user_request', 'generation_tasks', ['user_id', 'request_id']
        )
        return

    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if 'generation_tasks' not in tables:
        return
    columns = {column['name'] for column in inspector.get_columns('generation_tasks')}
    if 'request_id' not in columns:
        op.add_column('generation_tasks', sa.Column('request_id', sa.String(128), nullable=True))
    constraints = {item['name'] for item in inspector.get_unique_constraints('generation_tasks')}
    if 'uk_generation_tasks_user_request' not in constraints:
        op.create_unique_constraint(
            'uk_generation_tasks_user_request', 'generation_tasks', ['user_id', 'request_id']
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_constraint('uk_generation_tasks_user_request', 'generation_tasks', type_='unique')
        op.drop_column('generation_tasks', 'request_id')
        return

    inspector = inspect(op.get_bind())
    if 'generation_tasks' not in inspector.get_table_names():
        return
    constraints = {item['name'] for item in inspector.get_unique_constraints('generation_tasks')}
    if 'uk_generation_tasks_user_request' in constraints:
        op.drop_constraint('uk_generation_tasks_user_request', 'generation_tasks', type_='unique')
    columns = {column['name'] for column in inspector.get_columns('generation_tasks')}
    if 'request_id' in columns:
        op.drop_column('generation_tasks', 'request_id')
