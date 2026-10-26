"""Prevent concurrent queued/running collection runs for one source."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_collection_active_source_guard'
down_revision = '20261002_collection_execution_leases'
branch_labels = None
depends_on = None

INDEX_NAME = 'uk_collection_runs_active_source'


def upgrade() -> None:
    if context.is_offline_mode():
        op.create_index(
            INDEX_NAME,
            'collection_runs',
            ['source_id'],
            unique=True,
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )
        return

    bind = op.get_bind()
    inspector = inspect(bind)
    if 'collection_runs' not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspector.get_indexes('collection_runs')}
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            'collection_runs',
            ['source_id'],
            unique=True,
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if context.is_offline_mode():
        op.drop_index(INDEX_NAME, table_name='collection_runs')
        return

    inspector = inspect(bind)
    if 'collection_runs' in inspector.get_table_names() and INDEX_NAME in {
        item['name'] for item in inspector.get_indexes('collection_runs')
    }:
        op.drop_index(INDEX_NAME, table_name='collection_runs')
