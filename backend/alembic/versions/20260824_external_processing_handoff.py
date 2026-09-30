"""Add the external processing handoff contract without renaming PipeSight tables."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect

revision = '20260824_external_processing_handoff'
down_revision = '20260814_fix_version_width'
branch_labels = None
depends_on = None

_COLUMNS = {
    'data_sources': (
        ('handoff_mode', sa.String(16), sa.text("'external'")),
        ('processor_source_code', sa.String(128), None),
    ),
    'collection_runs': (
        ('handoff_status', sa.String(32), sa.text("'pending'")),
        ('handoff_batch_id', sa.String(64), None),
        ('handoff_count', sa.Integer(), sa.text('0')),
        ('handoff_processed_count', sa.Integer(), sa.text('0')),
        ('handoff_failed_count', sa.Integer(), sa.text('0')),
        ('handoff_time', sa.DateTime(), None),
        ('handoff_error', sa.Text(), None),
    ),
    'news_articles': (
        ('handoff_status', sa.String(32), sa.text("'pending'")),
        ('handoff_batch_id', sa.String(64), None),
        ('handoff_record_id', sa.String(128), None),
        ('handoff_trace_id', sa.String(64), None),
        ('handoff_version', sa.String(64), None),
        ('handoff_result_json', sa.JSON(), sa.text("'{}'")),
        ('handoff_time', sa.DateTime(), None),
        ('handoff_error', sa.Text(), None),
    ),
    'papers': (
        ('handoff_status', sa.String(32), sa.text("'pending'")),
        ('handoff_batch_id', sa.String(64), None),
        ('handoff_record_id', sa.String(128), None),
        ('handoff_trace_id', sa.String(64), None),
        ('handoff_version', sa.String(64), None),
        ('handoff_result_json', sa.JSON(), sa.text("'{}'")),
        ('handoff_time', sa.DateTime(), None),
        ('handoff_error', sa.Text(), None),
    ),
}

_CHECKS = {
    'data_sources': (
        ('ck_data_sources_handoff_mode', "handoff_mode IN ('local', 'external')"),
    ),
    'collection_runs': (
        (
            'ck_collection_runs_handoff_status',
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed')",
        ),
        (
            'ck_collection_runs_handoff_counters',
            'handoff_count >= 0 AND handoff_processed_count >= 0 AND handoff_failed_count >= 0',
        ),
    ),
    'news_articles': (
        (
            'ck_news_articles_handoff_status',
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')",
        ),
    ),
    'papers': (
        (
            'ck_papers_handoff_status',
            "handoff_status IN ('pending', 'dispatched', 'processing', 'completed', 'partial', 'failed', 'rejected')",
        ),
    ),
}

_INDEXES = (
    ('idx_collection_runs_handoff_status_time', 'collection_runs', ('handoff_status', 'create_time')),
    ('idx_news_articles_handoff_status_time', 'news_articles', ('handoff_status', 'update_time')),
    ('idx_papers_handoff_status_time', 'papers', ('handoff_status', 'update_time')),
)


def _online() -> bool:
    return not context.is_offline_mode()


def upgrade() -> None:
    # The full-system revision already creates these columns in fresh databases.
    # Offline SQL is generated from that baseline; existing databases use online inspection below.
    if context.is_offline_mode():
        return
    inspector = inspect(op.get_bind()) if _online() else None
    existing_tables = set(inspector.get_table_names()) if inspector else set(_COLUMNS)

    for table_name, columns in _COLUMNS.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {item['name'] for item in inspector.get_columns(table_name)} if inspector else set()
        for column_name, column_type, default in columns:
            if column_name in existing_columns:
                continue
            if op.get_bind().dialect.name == 'mysql' and isinstance(column_type, sa.JSON) and default is not None:
                op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))
                op.execute(f'UPDATE {table_name} SET {column_name} = JSON_OBJECT() WHERE {column_name} IS NULL')
                op.alter_column(table_name, column_name, existing_type=column_type, nullable=False)
                continue
            kwargs = {'nullable': default is None}
            if default is not None:
                kwargs['server_default'] = default
            op.add_column(table_name, sa.Column(column_name, column_type, **kwargs))

    for table_name, checks in _CHECKS.items():
        if table_name not in existing_tables:
            continue
        existing_checks = (
            {item['name'] for item in inspector.get_check_constraints(table_name) if item.get('name')}
            if inspector
            else set()
        )
        for constraint_name, expression in checks:
            if constraint_name not in existing_checks:
                op.create_check_constraint(constraint_name, table_name, expression)

    existing_indexes = (
        {(item['name'], table_name) for table_name in existing_tables for item in inspector.get_indexes(table_name)}
        if inspector
        else set()
    )
    for index_name, table_name, columns in _INDEXES:
        if table_name in existing_tables and (index_name, table_name) not in existing_indexes:
            op.create_index(index_name, table_name, list(columns))


def downgrade() -> None:
    for index_name, table_name, _ in reversed(_INDEXES):
        op.drop_index(index_name, table_name=table_name)
    for table_name, checks in reversed(tuple(_CHECKS.items())):
        for constraint_name, _ in reversed(checks):
            op.drop_constraint(constraint_name, table_name, type_='check')
    for table_name, columns in reversed(tuple(_COLUMNS.items())):
        for column_name, _, _ in reversed(columns):
            op.drop_column(table_name, column_name)
