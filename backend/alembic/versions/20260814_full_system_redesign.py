"""Adopt the final 23-table PipeSight schema without deleting unrelated legacy data."""

import re
from pathlib import Path

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy import inspect, text

revision = '20260814_full_system_redesign'
down_revision = '20260814_simplify_domain'
branch_labels = None
depends_on = None

_DEFERRED_TABLES = (
    'report_exports',
    'report_citations',
    'generation_task_items',
    'knowledge_chunks',
    'prompt_versions',
    'report_templates',
    'resource_terms',
    'taxonomy_terms',
    'collection_records',
)


def _schema_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[2] / 'sql' / filename


def _execute_schema_file(filename: str) -> None:
    sql = _schema_path(filename).read_text(encoding='utf-8-sig')
    sql = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    for raw_statement in sql.split(';'):
        statement = raw_statement.strip()
        if statement:
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
                    if index_name in {item['name'] for item in inspector.get_indexes(table_name)}:
                        continue
                    table_columns = {item['name'] for item in inspector.get_columns(table_name)}
                    if any(column.strip().strip('`"') not in table_columns for column in columns_sql.split(',')):
                        continue
                    statement = re.sub(r'IF NOT EXISTS\s+', '', statement, count=1, flags=re.IGNORECASE)
            op.execute(statement)


def _columns(table_name: str) -> set[str]:
    return {item['name'] for item in inspect(op.get_bind()).get_columns(table_name)}


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return
    columns = {item['name']: item for item in inspector.get_columns(table_name)}
    if old_name in columns and new_name not in columns:
        column = columns[old_name]
        op.alter_column(
            table_name,
            old_name,
            new_column_name=new_name,
            existing_type=column['type'],
            existing_nullable=column.get('nullable'),
            existing_server_default=column.get('default'),
            existing_comment=column.get('comment'),
            existing_autoincrement=column.get('autoincrement'),
        )


def _rename_business_columns() -> None:
    _rename_column_if_needed('knowledge_files', 'material_id', 'file_id')
    _rename_column_if_needed('user_saved_items', 'workspace_item_id', 'saved_item_id')
    _rename_column_if_needed('generation_tasks', 'job_id', 'task_id')
    _rename_column_if_needed('reports', 'job_id', 'source_task_id')


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        bind = op.get_bind()
        if bind.dialect.name == 'mysql' and isinstance(column.type, sa.JSON) and column.server_default is not None:
            # MySQL versions used by existing deployments reject JSON defaults.
            # Backfill after adding the nullable column, then enforce NOT NULL.
            op.add_column(table_name, sa.Column(column.name, column.type, nullable=True))
            default_value = str(column.server_default.arg).strip("'\"")
            expression = 'JSON_ARRAY()' if default_value == '[]' else 'JSON_OBJECT()'
            op.execute(f'UPDATE {table_name} SET {column.name} = {expression} WHERE {column.name} IS NULL')
            op.alter_column(table_name, column.name, existing_type=column.type, nullable=False)
            return
        op.add_column(table_name, column)


def _index_names(table_name: str) -> set[str]:
    return {item['name'] for item in inspect(op.get_bind()).get_indexes(table_name)}


def _add_index(table_name: str, name: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=unique)


def _constraint_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    names = {item.get('name') for item in inspector.get_unique_constraints(table_name)}
    names.update(item.get('name') for item in inspector.get_foreign_keys(table_name))
    return {name for name in names if name}


def _check_constraint_names(table_name: str) -> set[str]:
    return {
        item.get('name')
        for item in inspect(op.get_bind()).get_check_constraints(table_name)
        if item.get('name')
    }


def _has_duplicates(table_name: str, columns: list[str]) -> bool:
    quoted = ', '.join(columns)
    required = ' AND '.join(f'{column} IS NOT NULL' for column in columns)
    statement = text(f'SELECT 1 FROM {table_name} WHERE {required} GROUP BY {quoted} HAVING COUNT(*) > 1 LIMIT 1')
    return op.get_bind().execute(statement).first() is not None


def _add_unique(table_name: str, name: str, columns: list[str]) -> None:
    if name in _constraint_names(table_name):
        return
    if _has_duplicates(table_name, columns):
        raise RuntimeError(f'{table_name} contains duplicate values for {columns}; clean the data before migration')
    op.create_unique_constraint(name, table_name, columns)


def _has_orphans(table_name: str, column: str, target_table: str, target_column: str) -> bool:
    statement = text(
        f'SELECT 1 FROM {table_name} child LEFT JOIN {target_table} parent '
        f'ON child.{column} = parent.{target_column} '
        f'WHERE child.{column} IS NOT NULL AND parent.{target_column} IS NULL LIMIT 1'
    )
    return op.get_bind().execute(statement).first() is not None


def _add_foreign_key(
    table_name: str,
    name: str,
    column: str,
    target_table: str,
    target_column: str,
    *,
    ondelete: str,
) -> None:
    if _has_orphans(table_name, column, target_table, target_column):
        raise RuntimeError(
            f'{table_name}.{column} contains orphan values for {target_table}.{target_column}; '
            'clean the data before migration'
        )
    existing_foreign_keys = inspect(op.get_bind()).get_foreign_keys(table_name)
    for item in existing_foreign_keys:
        same_shape = (
            item.get('constrained_columns') == [column]
            and item.get('referred_table') == target_table
            and item.get('referred_columns') == [target_column]
        )
        if item.get('name') != name and not same_shape:
            continue
        existing_ondelete = str((item.get('options') or {}).get('ondelete') or '').upper()
        if same_shape and existing_ondelete == ondelete.upper():
            return
        if item.get('name'):
            op.drop_constraint(item['name'], table_name, type_='foreignkey')
        break
    op.create_foreign_key(name, table_name, target_table, [column], [target_column], ondelete=ondelete)


def _add_business_columns() -> None:
    _add_column('sys_job_log', sa.Column('job_id', sa.BigInteger(), nullable=True))

    _add_column('data_sources', sa.Column('source_code', sa.String(100), nullable=True))
    _add_column('data_sources', sa.Column('adapter_key', sa.String(128), nullable=True))
    _add_column('data_sources', sa.Column('consecutive_failures', sa.Integer(), server_default='0', nullable=False))
    op.execute("UPDATE data_sources SET source_code = source_id WHERE source_code IS NULL OR source_code = ''")
    op.execute("UPDATE data_sources SET adapter_key = source_type WHERE adapter_key IS NULL OR adapter_key = ''")
    op.alter_column('data_sources', 'source_code', existing_type=sa.String(100), nullable=False)
    op.alter_column('data_sources', 'adapter_key', existing_type=sa.String(128), nullable=False)

    _add_column('collection_runs', sa.Column('scheduler_job_id', sa.BigInteger(), nullable=True))
    _add_column('collection_runs', sa.Column('config_snapshot', sa.JSON(), server_default='{}', nullable=False))
    _add_column('collection_runs', sa.Column('update_time', sa.DateTime(), nullable=True))

    _add_column('news_articles', sa.Column('url_hash', sa.String(128), nullable=True))
    _add_column('news_articles', sa.Column('source_name', sa.String(255), nullable=True))
    _add_column('news_articles', sa.Column('analysis_version', sa.String(64), nullable=True))

    _add_column('papers', sa.Column('source_name', sa.String(255), nullable=True))
    _add_column('papers', sa.Column('authors_json', sa.JSON(), server_default='[]', nullable=False))
    _add_column('papers', sa.Column('keywords', sa.JSON(), server_default='[]', nullable=False))
    _add_column('papers', sa.Column('doi_normalized', sa.String(255), nullable=True))
    _add_column('papers', sa.Column('open_access_status', sa.String(32), server_default='unknown', nullable=False))
    _add_column('papers', sa.Column('review_status', sa.String(32), server_default='pending', nullable=False))
    _add_column('papers', sa.Column('permission_scope', sa.String(32), server_default='public', nullable=False))
    op.execute('UPDATE papers SET doi_normalized = LOWER(TRIM(doi)) WHERE doi IS NOT NULL AND doi_normalized IS NULL')

    _add_column('knowledge_files', sa.Column('file_hash', sa.String(128), nullable=True))
    _add_column('knowledge_files', sa.Column('allow_download', sa.Boolean(), server_default=sa.true(), nullable=False))
    _add_column('knowledge_files', sa.Column('allow_ai_use', sa.Boolean(), server_default=sa.true(), nullable=False))

    _add_column('report_versions', sa.Column('quality_issues', sa.JSON(), server_default='[]', nullable=False))
    _add_column('report_versions', sa.Column('model_snapshot', sa.JSON(), server_default='{}', nullable=False))


def _add_platform_constraints() -> None:
    unique_specs = [
        ('sys_user', 'uk_sys_user_user_name', ['user_name']),
        ('sys_role', 'uk_sys_role_role_key', ['role_key']),
        ('sys_role', 'uk_sys_role_role_name', ['role_name']),
        ('sys_dict_data', 'uk_sys_dict_data_type_value', ['dict_type', 'dict_value']),
        ('sys_config', 'uk_sys_config_config_key', ['config_key']),
        ('sys_job', 'uk_sys_job_name_group', ['job_name', 'job_group']),
        ('ai_models', 'uk_ai_models_owner_provider_code', ['user_id', 'provider', 'model_code']),
    ]
    for table_name, name, columns in unique_specs:
        _add_unique(table_name, name, columns)

    index_specs = [
        ('sys_user', 'idx_sys_user_status', ['status', 'del_flag']),
        ('sys_user', 'idx_sys_user_phone', ['phonenumber']),
        ('sys_role', 'idx_sys_role_status', ['status', 'del_flag']),
        ('sys_menu', 'idx_sys_menu_parent_sort', ['parent_id', 'order_num']),
        ('sys_menu', 'idx_sys_menu_status_visible', ['status', 'visible']),
        ('sys_config', 'idx_sys_config_type', ['config_type']),
        ('sys_job', 'idx_sys_job_status_group', ['status', 'job_group']),
        ('sys_job_log', 'idx_sys_job_log_job_time', ['job_id', 'create_time']),
        ('ai_models', 'idx_ai_models_type_status_sort', ['model_type', 'status', 'model_sort']),
    ]
    for table_name, name, columns in index_specs:
        _add_index(table_name, name, columns)

    foreign_key_specs = [
        ('sys_user_role', 'fk_sys_user_role_user', 'user_id', 'sys_user', 'user_id', 'CASCADE'),
        ('sys_user_role', 'fk_sys_user_role_role', 'role_id', 'sys_role', 'role_id', 'CASCADE'),
        ('sys_role_menu', 'fk_sys_role_menu_role', 'role_id', 'sys_role', 'role_id', 'CASCADE'),
        ('sys_role_menu', 'fk_sys_role_menu_menu', 'menu_id', 'sys_menu', 'menu_id', 'CASCADE'),
        ('sys_dict_data', 'fk_sys_dict_data_type', 'dict_type', 'sys_dict_type', 'dict_type', 'CASCADE'),
        ('sys_job_log', 'fk_sys_job_log_job', 'job_id', 'sys_job', 'job_id', 'SET NULL'),
        ('ai_models', 'fk_ai_models_user', 'user_id', 'sys_user', 'user_id', 'CASCADE'),
        ('ai_chat_config', 'fk_ai_chat_config_user', 'user_id', 'sys_user', 'user_id', 'CASCADE'),
    ]
    for table_name, name, column, target_table, target_column, ondelete in foreign_key_specs:
        _add_foreign_key(table_name, name, column, target_table, target_column, ondelete=ondelete)


def _add_business_constraints() -> None:
    old_unique = {item.get('name') for item in inspect(op.get_bind()).get_unique_constraints('user_saved_items')}
    if 'uk_user_saved_items_user_item_action' in old_unique:
        op.drop_constraint('uk_user_saved_items_user_item_action', 'user_saved_items', type_='unique')
    _add_unique(
        'user_saved_items',
        'uk_user_saved_items_target_action',
        ['user_id', 'item_type', 'item_id', 'action'],
    )
    _add_unique('data_sources', 'uk_data_sources_code', ['source_code'])
    _add_unique('news_articles', 'uk_news_articles_url_hash', ['url_hash'])
    _add_unique('papers', 'uk_papers_doi_normalized', ['doi_normalized'])

    _add_index('knowledge_files', 'idx_knowledge_files_owner_time', ['owner_id', 'update_time'])
    _add_index('generation_tasks', 'idx_generation_tasks_user_status_time', ['user_id', 'status', 'update_time'])
    _add_index('reports', 'idx_reports_user_status_time', ['user_id', 'status', 'update_time'])
    _add_index('user_saved_items', 'idx_user_saved_items_target', ['item_type', 'item_id'])

    foreign_key_specs = [
        ('knowledge_files', 'fk_knowledge_files_owner', 'owner_id', 'sys_user', 'user_id', 'RESTRICT'),
        ('user_saved_items', 'fk_user_saved_items_user', 'user_id', 'sys_user', 'user_id', 'CASCADE'),
        ('generation_tasks', 'fk_generation_tasks_user', 'user_id', 'sys_user', 'user_id', 'RESTRICT'),
        ('reports', 'fk_reports_source_task', 'source_task_id', 'generation_tasks', 'task_id', 'SET NULL'),
        ('reports', 'fk_reports_user', 'user_id', 'sys_user', 'user_id', 'RESTRICT'),
        ('report_versions', 'fk_report_versions_report', 'report_id', 'reports', 'report_id', 'CASCADE'),
        ('data_sources', 'fk_data_sources_owner', 'owner_id', 'sys_user', 'user_id', 'SET NULL'),
        ('collection_runs', 'fk_collection_runs_source', 'source_id', 'data_sources', 'source_id', 'RESTRICT'),
        ('collection_runs', 'fk_collection_runs_scheduler_job', 'scheduler_job_id', 'sys_job', 'job_id', 'SET NULL'),
        ('news_articles', 'fk_news_articles_source', 'source_id', 'data_sources', 'source_id', 'SET NULL'),
        ('news_articles', 'fk_news_articles_run', 'collection_run_id', 'collection_runs', 'run_id', 'SET NULL'),
        ('papers', 'fk_papers_source', 'source_id', 'data_sources', 'source_id', 'SET NULL'),
        ('papers', 'fk_papers_run', 'collection_run_id', 'collection_runs', 'run_id', 'SET NULL'),
    ]
    for table_name, name, column, target_table, target_column, ondelete in foreign_key_specs:
        _add_foreign_key(table_name, name, column, target_table, target_column, ondelete=ondelete)


def _drop_column_if_unused(table_name: str, column_name: str, *, validation_sql: str | None = None) -> None:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return
    columns = {item['name'] for item in inspector.get_columns(table_name)}
    if column_name not in columns:
        return
    if validation_sql and op.get_bind().execute(text(validation_sql)).first():
        raise RuntimeError(f'{table_name}.{column_name} still contains non-migrated data')
    for foreign_key in inspector.get_foreign_keys(table_name):
        if column_name in foreign_key.get('constrained_columns', []) and foreign_key.get('name'):
            op.drop_constraint(foreign_key['name'], table_name, type_='foreignkey')
    for index in inspector.get_indexes(table_name):
        if column_name in (index.get('column_names') or []) and index.get('name'):
            op.drop_index(index['name'], table_name=table_name)
    op.drop_column(table_name, column_name)


def _remove_deferred_schema() -> None:
    connection = op.get_bind()
    _drop_column_if_unused(
        'generation_tasks',
        'report_id',
        validation_sql=(
            'SELECT 1 FROM generation_tasks task LEFT JOIN reports report '
            'ON report.source_task_id = task.task_id AND report.report_id = task.report_id '
            'WHERE task.report_id IS NOT NULL AND report.report_id IS NULL LIMIT 1'
        ),
    )
    _drop_column_if_unused(
        'generation_tasks',
        'prompt_version_id',
        validation_sql='SELECT 1 FROM generation_tasks WHERE prompt_version_id IS NOT NULL LIMIT 1',
    )
    generation_columns = {item['name'] for item in inspect(connection).get_columns('generation_tasks')}
    if 'template_id' in generation_columns:
        for foreign_key in inspect(connection).get_foreign_keys('generation_tasks'):
            if 'template_id' in (foreign_key.get('constrained_columns') or []) and foreign_key.get('name'):
                op.drop_constraint(foreign_key['name'], 'generation_tasks', type_='foreignkey')

    for table_name, column_name in (
        ('news_articles', 'raw_record_id'),
        ('papers', 'raw_record_id'),
    ):
        _drop_column_if_unused(
            table_name,
            column_name,
            validation_sql=f'SELECT 1 FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 1',
        )

    for table_name in _DEFERRED_TABLES:
        if table_name not in set(inspect(connection).get_table_names()):
            continue
        if connection.execute(text(f'SELECT 1 FROM {table_name} LIMIT 1')).first():
            raise RuntimeError(f'{table_name} contains data; archive it before final schema migration')
        op.drop_table(table_name)

    for table_name, column_name in (
        ('data_sources', 'deleted_at'),
        ('knowledge_files', 'deleted_at'),
        ('reports', 'deleted_at'),
    ):
        _drop_column_if_unused(
            table_name,
            column_name,
            validation_sql=f'SELECT 1 FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT 1',
        )


def _add_check(table_name: str, name: str, condition: str) -> None:
    if name not in _check_constraint_names(table_name):
        op.create_check_constraint(name, table_name, condition)


def _finalize_constraints() -> None:
    connection = op.get_bind()
    # Older RuoYi seeds used 2/3/4 for department-scoped roles. Departments
    # are intentionally removed, so map those legacy scopes to "own data".
    connection.execute(text("UPDATE sys_role SET data_scope = '5' WHERE data_scope IS NULL OR data_scope NOT IN ('1', '5')"))
    if connection.execute(text('SELECT 1 FROM ai_models WHERE user_id IS NULL LIMIT 1')).first():
        raise RuntimeError('ai_models.user_id contains NULL values; assign an owner before migration')

    ai_unique_names = {
        item.get('name') for item in inspect(connection).get_unique_constraints('ai_models') if item.get('name')
    }
    if 'uk_ai_models_provider_code' in ai_unique_names:
        op.drop_constraint('uk_ai_models_provider_code', 'ai_models', type_='unique')
    ai_user_column = next(item for item in inspect(connection).get_columns('ai_models') if item['name'] == 'user_id')
    if ai_user_column.get('nullable'):
        op.alter_column('ai_models', 'user_id', existing_type=ai_user_column['type'], nullable=False)
    _add_foreign_key('ai_models', 'fk_ai_models_user', 'user_id', 'sys_user', 'user_id', ondelete='CASCADE')

    check_specs = (
        ('sys_user', 'ck_sys_user_status', "status IN ('0', '1')"),
        ('sys_user', 'ck_sys_user_del_flag', "del_flag IN ('0', '2')"),
        ('sys_user', 'ck_sys_user_sex', "sex IN ('0', '1', '2')"),
        ('sys_role', 'ck_sys_role_data_scope', "data_scope IN ('1', '5')"),
        ('sys_role', 'ck_sys_role_status', "status IN ('0', '1')"),
        ('sys_role', 'ck_sys_role_del_flag', "del_flag IN ('0', '2')"),
        ('ai_models', 'ck_ai_models_max_tokens', 'max_tokens IS NULL OR max_tokens > 0'),
        ('ai_models', 'ck_ai_models_temperature', 'temperature IS NULL OR temperature BETWEEN 0 AND 2'),
        ('ai_models', 'ck_ai_models_support_reasoning', "support_reasoning IN ('Y', 'N')"),
        ('ai_models', 'ck_ai_models_support_images', "support_images IN ('Y', 'N')"),
        ('ai_models', 'ck_ai_models_status', "status IN ('0', '1')"),
        ('knowledge_files', 'ck_knowledge_files_permission_scope', "permission_scope IN ('private', 'public')"),
        ('knowledge_files', 'ck_knowledge_files_parse_status', "parse_status IN ('queued', 'parsing', 'indexed', 'failed')"),
        ('knowledge_files', 'ck_knowledge_files_file_size', 'file_size >= 0'),
        ('knowledge_files', 'ck_knowledge_files_version_no', 'version_no >= 1'),
        ('user_saved_items', 'ck_user_saved_items_item_type', "item_type IN ('material', 'article', 'paper', 'report')"),
        ('user_saved_items', 'ck_user_saved_items_action', "action IN ('favorite', 'basket')"),
        ('generation_tasks', 'ck_generation_tasks_status', "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"),
        ('generation_tasks', 'ck_generation_tasks_progress', 'progress BETWEEN 0 AND 100'),
        ('reports', 'ck_reports_status', "status IN ('draft', 'reviewing', 'completed', 'published', 'archived')"),
        ('reports', 'ck_reports_version_no', 'version_no >= 1'),
        ('reports', 'ck_reports_word_count', 'word_count >= 0'),
        ('report_versions', 'ck_report_versions_version_no', 'version_no >= 1'),
        ('report_versions', 'ck_report_versions_source', "source IN ('generated', 'retry', 'manual', 'autosave', 'publish', 'restored')"),
        ('data_sources', 'ck_data_sources_status', "status IN ('active', 'inactive')"),
        ('data_sources', 'ck_data_sources_counters', 'success_count >= 0 AND failure_count >= 0 AND consecutive_failures >= 0'),
        ('collection_runs', 'ck_collection_runs_trigger_type', "trigger_type IN ('schedule', 'manual', 'retry')"),
        ('collection_runs', 'ck_collection_runs_status', "status IN ('queued', 'running', 'success', 'failed', 'cancelled')"),
        ('collection_runs', 'ck_collection_runs_counters', 'fetched_count >= 0 AND inserted_count >= 0 AND updated_count >= 0 AND duplicate_count >= 0 AND failed_count >= 0'),
        ('news_articles', 'ck_news_articles_type', "article_type IN ('news', 'wechat')"),
        ('news_articles', 'ck_news_articles_relevance', 'relevance_score BETWEEN 0 AND 100'),
        ('news_articles', 'ck_news_articles_review_status', "review_status IN ('pending', 'approved', 'rejected')"),
        ('news_articles', 'ck_news_articles_permission_scope', "permission_scope IN ('private', 'public')"),
        ('papers', 'ck_papers_publication_year', 'publication_year IS NULL OR publication_year >= 1600'),
        ('papers', 'ck_papers_citation_count', 'citation_count >= 0'),
        ('papers', 'ck_papers_review_status', "review_status IN ('pending', 'approved', 'rejected')"),
        ('papers', 'ck_papers_permission_scope', "permission_scope IN ('private', 'public')"),
    )
    for table_name, name, condition in check_specs:
        _add_check(table_name, name, condition)


def upgrade() -> None:
    if context.is_offline_mode():
        dialect = op.get_bind().dialect.name
        suffix = '-pg.sql' if dialect == 'postgresql' else '.sql'
        _execute_schema_file(f'pipeline-domain{suffix}')
        _execute_schema_file(f'pipeline-domain-enhancement{suffix}')
        return

    dialect = op.get_bind().dialect.name
    suffix = '-pg.sql' if dialect == 'postgresql' else '.sql'
    _rename_business_columns()
    _execute_schema_file(f'pipeline-domain{suffix}')
    _execute_schema_file(f'pipeline-domain-enhancement{suffix}')
    _add_business_columns()
    _add_platform_constraints()
    _add_business_constraints()
    _remove_deferred_schema()
    _finalize_constraints()


def downgrade() -> None:
    # This adoption revision is intentionally non-destructive. Removing the new
    # schema requires an explicit, reviewed data-retirement migration.
    return None
