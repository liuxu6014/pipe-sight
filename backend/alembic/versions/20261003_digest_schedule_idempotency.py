"""Add idempotency keys for digest schedule creation."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20261003_digest_schedule_idempotency'
down_revision = '20261003_report_publication_permission'
branch_labels = None
depends_on = None

TABLE_NAME = 'digest_schedules'
COLUMN_NAME = 'request_id'
INDEX_NAME = 'uk_digest_schedules_user_request'


def upgrade() -> None:
    if context.is_offline_mode():
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.String(128), nullable=True, comment='客户端幂等请求标识'))
        op.create_index(INDEX_NAME, TABLE_NAME, ['user_id', COLUMN_NAME], unique=True)
        return
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    columns = {item['name'] for item in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.String(128), nullable=True, comment='客户端幂等请求标识'))
    indexes = {item['name'] for item in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME not in indexes:
        op.create_index(INDEX_NAME, TABLE_NAME, ['user_id', COLUMN_NAME], unique=True)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
        op.drop_column(TABLE_NAME, COLUMN_NAME)
        return
    inspector = inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return
    indexes = {item['name'] for item in inspector.get_indexes(TABLE_NAME)}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
    columns = {item['name'] for item in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME in columns:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
