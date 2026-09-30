"""Create the first explicit PipeSight domain schema.

The framework tables keep the RuoYi ``sys_*``/``gen_*``/``ai_*`` names because
login, permissions and the management UI depend on them. Application tables
use explicit business names and only include implemented product capabilities.
"""

import re
from pathlib import Path

from alembic import context, op
from sqlalchemy import inspect, text

revision = '20260814_pipeline_domain'
down_revision = None
branch_labels = None
depends_on = None

_LEGACY_RENAMES = [
    ('pipeline_material', 'knowledge_files'),
    ('materials', 'knowledge_files'),
    ('pipeline_workspace_item', 'user_saved_items'),
    ('workspace_items', 'user_saved_items'),
    ('pipeline_research_job', 'generation_tasks'),
    ('jobs', 'generation_tasks'),
    ('pipeline_report', 'reports'),
    ('pipeline_report_version', 'report_versions'),
    ('pipeline_source', 'data_sources'),
    ('sources', 'data_sources'),
    ('pipeline_crawl_run', 'collection_runs'),
    ('crawl_runs', 'collection_runs'),
    ('crawl_tasks', 'collection_runs'),
]

_DOMAIN_TABLES = [
    'papers',
    'news_articles',
    'collection_runs',
    'data_sources',
    'report_versions',
    'reports',
    'generation_tasks',
    'user_saved_items',
    'knowledge_files',
]


def _schema_path(filename: str) -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / 'sql' / filename


def _rename_legacy_tables() -> None:
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    existing = set(inspect(connection).get_table_names())
    for old_name, new_name in _LEGACY_RENAMES:
        if old_name in existing and new_name not in existing:
            op.rename_table(old_name, new_name)
            existing.remove(old_name)
            existing.add(new_name)


def _execute_schema_file(filename: str) -> None:
    sql = _schema_path(filename).read_text(encoding='utf-8-sig')
    sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    for raw_statement in sql.split(';'):
        statement = raw_statement.strip()
        if statement:
            # MySQL has no CREATE INDEX IF NOT EXISTS. Keep the seed SQL
            # idempotent by checking the catalog before issuing the DDL.
            if (
                not context.is_offline_mode()
                and op.get_bind().dialect.name == 'mysql'
                and statement.upper().startswith('CREATE INDEX IF NOT EXISTS')
            ):
                match = re.match(
                    r'CREATE INDEX IF NOT EXISTS\s+(\w+)\s+ON\s+(\w+)\s*\(([^)]*)\)',
                    statement,
                    re.IGNORECASE,
                )
                if match:
                    index_name, table_name, columns_sql = match.groups()
                    inspector = inspect(op.get_bind())
                    existing = {item['name'] for item in inspector.get_indexes(table_name)}
                    if index_name in existing:
                        continue
                    table_columns = {item['name'] for item in inspector.get_columns(table_name)}
                    if any(column.strip().strip('`"') not in table_columns for column in columns_sql.split(',')):
                        # Older installations receive these columns from the
                        # dedicated handoff migration later in the chain.
                        continue
                    statement = re.sub(r'IF NOT EXISTS\s+', '', statement, count=1, flags=re.IGNORECASE)
            op.execute(statement)


def _normalize_sys_job_primary_key() -> None:
    """Allow domain foreign keys to target legacy RuoYi job tables safely."""
    if context.is_offline_mode():
        return
    connection = op.get_bind()
    inspector = inspect(connection)
    if 'sys_job' not in inspector.get_table_names():
        return
    primary_key = inspector.get_pk_constraint('sys_job')
    if primary_key.get('constrained_columns') == ['job_id']:
        return
    duplicate = connection.execute(
        text('SELECT 1 FROM sys_job GROUP BY job_id HAVING COUNT(*) > 1 LIMIT 1')
    ).first()
    if duplicate:
        raise RuntimeError('sys_job.job_id contains duplicates and cannot become the single primary key')
    if connection.dialect.name == 'mysql':
        op.execute('ALTER TABLE sys_job DROP PRIMARY KEY, ADD PRIMARY KEY (job_id)')
        return
    constraint_name = primary_key.get('name')
    if constraint_name:
        op.drop_constraint(constraint_name, 'sys_job', type_='primary')
    op.create_primary_key('pk_sys_job', 'sys_job', ['job_id'])


def upgrade() -> None:
    _rename_legacy_tables()
    _normalize_sys_job_primary_key()
    dialect = op.get_bind().dialect.name
    suffix = '-pg.sql' if dialect == 'postgresql' else '.sql'
    _execute_schema_file(f'pipeline-domain{suffix}')
    _execute_schema_file(f'pipeline-domain-enhancement{suffix}')


def downgrade() -> None:
    for table_name in _DOMAIN_TABLES:
        op.execute(f'DROP TABLE IF EXISTS {table_name}')
