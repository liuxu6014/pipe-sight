"""Allow Alembic revision identifiers longer than 32 characters."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect


revision = '20260814_fix_version_width'
down_revision = '20260814_remove_unused_platform'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if context.is_offline_mode():
        if dialect == 'postgresql':
            op.execute('ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)')
        else:
            op.execute('ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(64) NOT NULL')
        return

    inspector = inspect(bind)
    if 'alembic_version' not in inspector.get_table_names():
        return
    columns = {item['name']: item for item in inspector.get_columns('alembic_version')}
    column = columns.get('version_num')
    if column is None or (getattr(column['type'], 'length', None) or 0) >= 64:
        return
    op.alter_column(
        'alembic_version',
        'version_num',
        existing_type=column['type'],
        type_=sa.String(length=64),
        existing_nullable=column.get('nullable', False),
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if context.is_offline_mode():
        if dialect == 'postgresql':
            op.execute('ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)')
        else:
            op.execute('ALTER TABLE alembic_version MODIFY COLUMN version_num VARCHAR(32) NOT NULL')
        return

    inspector = inspect(bind)
    if 'alembic_version' not in inspector.get_table_names():
        return
    column = next(
        (item for item in inspector.get_columns('alembic_version') if item['name'] == 'version_num'),
        None,
    )
    if column is None:
        return
    op.alter_column(
        'alembic_version',
        'version_num',
        existing_type=column['type'],
        type_=sa.String(length=32),
        existing_nullable=column.get('nullable', False),
    )
