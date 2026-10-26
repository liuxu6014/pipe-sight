"""Canonical application schema and frozen historical bootstrap SQL boundaries.

27 application ORM tables plus APScheduler/Alembic's two framework tables make
the approved 29-table target. Baseline SQL deliberately remains the old layout.
All DDL and data checks use a private in-memory SQLite database.
"""

import hashlib
import re
import socket
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from sqlalchemy import Engine, UniqueConstraint, create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.models.registry import register_sqlalchemy_models
from app.infrastructure.schemas.online import OnlineModel
from app.system.schemas.role import RoleModel
from app.system.schemas.user import UserDetailModel, UserInfoModel, UserModel, UserProfileModel
from config.database import Base

register_sqlalchemy_models()

DOMAIN_TABLES = {
    'news_articles',
    'papers',
    'categories',
    'data_sources',
    'knowledge_files',
    'templates',
    'ai_models',
    'reports',
    'generation_tasks',
    'report_assets',
    'digest_schedules',
    'basket_items',
    'collection_runs',
}
FOUNDATION_TABLES = {
    'sys_user',
    'sys_role',
    'sys_menu',
    'sys_user_role',
    'sys_role_menu',
    'sys_config',
    'sys_dict_type',
    'sys_dict_data',
    'sys_logininfor',
    'sys_oper_log',
    'sys_job',
    'sys_job_log',
}
OPTIONAL_TABLES = {'model_calls', 'report_versions'}
FRAMEWORK_TABLES = {'apscheduler_jobs', 'alembic_version'}
APPLICATION_TABLES = DOMAIN_TABLES | FOUNDATION_TABLES | OPTIONAL_TABLES
FULL_TABLE_COUNT = 29
BASELINE_RUOYI_TABLES = {
    'sys_user',
    'sys_role',
    'sys_menu',
    'sys_user_role',
    'sys_role_menu',
    'sys_oper_log',
    'sys_dict_type',
    'sys_dict_data',
    'sys_config',
    'sys_logininfor',
    'sys_job',
    'sys_job_log',
    'ai_models',
    'ai_chat_config',
}
BASELINE_DOMAIN_TABLES = {
    'knowledge_files',
    'user_saved_items',
    'generation_tasks',
    'digest_schedules',
    'reports',
    'report_versions',
    'report_publications',
    'report_exports',
    'data_sources',
    'collection_runs',
    'news_articles',
    'papers',
    'pipeline_template_versions',
    'pipeline_prompt_versions',
    'pipeline_content_review_events',
    'pipeline_quality_issues',
    'pipeline_quality_issue_events',
    'pipeline_duplicate_groups',
    'pipeline_duplicate_members',
    'pipeline_duplicate_group_events',
    'pipeline_model_routes',
    'pipeline_model_route_usage',
    'pipeline_model_call_audits',
}
RETIRED_TABLES = {
    'chat_settings',
    'user_saved_items',
    'report_publications',
    'report_exports',
    'template_versions',
    'content_review_events',
    'quality_issues',
    'quality_issue_events',
    'duplicate_groups',
    'duplicate_members',
    'duplicate_group_events',
    'model_routes',
    'model_route_usage',
    'prompt_versions',
    'ai_chat_config',
} | {
    'users',
    'roles',
    'menus',
    'user_roles',
    'role_menus',
    'settings',
    'dict_types',
    'dict_items',
    'login_logs',
    'operation_logs',
    'scheduled_jobs',
    'job_logs',
}
DEFERRED_TABLES = {
    'collection_records',
    'taxonomy_terms',
    'resource_terms',
    'knowledge_chunks',
    'report_templates',
    'generation_task_items',
    'report_citations',
}
OBSOLETE_GENERIC_TABLES = {'contents', 'chunks', 'audit_logs', 'sources', 'crawl_tasks', 'articles'}
REMOVED_PLATFORM_TABLES = {
    'sys_dept',
    'sys_post',
    'sys_role_dept',
    'sys_user_post',
    'sys_notice',
    'gen_table',
    'gen_table_column',
}


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError('Schema checks must not connect to a real service')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


@pytest.fixture
def sqlite_schema() -> Generator[Engine]:
    engine = create_engine('sqlite:///:memory:')

    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection: Any, _record: Any) -> None:
        connection.execute('PRAGMA foreign_keys=ON')
        # Production indexes use PostgreSQL md5(url). Supply only the SQLite
        # test connection with the equivalent deterministic function.
        connection.create_function(
            'md5',
            1,
            lambda value: hashlib.md5(value.encode(), usedforsecurity=False).hexdigest(),
            deterministic=True,
        )

    try:
        Base.metadata.create_all(engine)
        # Obtain real framework definitions without starting a scheduler or
        # touching application metadata; never invent framework ORM classes.
        jobstore = SQLAlchemyJobStore(engine=engine)
        jobstore.jobs_t.create(engine)
        version_table = MigrationContext.configure(dialect_name='sqlite').impl.version_table_impl(
            version_table='alembic_version',
            version_table_schema=None,
            version_table_pk=True,
        )
        version_table.create(engine)
        yield engine
    finally:
        engine.dispose()


def test_domain_models_are_registered_and_sqlite_compatible(sqlite_schema: Engine) -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLES
    assert not (RETIRED_TABLES | DEFERRED_TABLES | REMOVED_PLATFORM_TABLES | OBSOLETE_GENERIC_TABLES) & set(
        Base.metadata.tables
    )
    assert set(inspect(sqlite_schema).get_table_names()) == APPLICATION_TABLES | FRAMEWORK_TABLES
    with sqlite_schema.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert not connection.exec_driver_sql('PRAGMA foreign_key_check').all()
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.key in APPLICATION_TABLES


def test_mysql_and_postgresql_domain_sql_have_the_same_table_set() -> None:
    # Baseline SQL is a frozen legacy layout; Alembic produces the current names.
    sql_dir = Path(__file__).parents[1] / 'sql'
    mysql_sql = (sql_dir / 'pipeline-domain.sql').read_text(encoding='utf-8') + (
        sql_dir / 'pipeline-domain-enhancement.sql'
    ).read_text(encoding='utf-8')
    pg_sql = (sql_dir / 'pipeline-domain-pg.sql').read_text(encoding='utf-8') + (
        sql_dir / 'pipeline-domain-enhancement-pg.sql'
    ).read_text(encoding='utf-8')
    for sql in (mysql_sql, pg_sql):
        baseline_tables = set(
            re.findall(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-z0-9_]+)', sql, flags=re.IGNORECASE)
        )
        assert baseline_tables == BASELINE_DOMAIN_TABLES
        assert not {'categories', 'basket_items', 'templates', 'report_assets'} & baseline_tables
    for baseline_name in BASELINE_DOMAIN_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {baseline_name}' in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {baseline_name}' in pg_sql
    for table_name in OBSOLETE_GENERIC_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in pg_sql
    for table_name in DEFERRED_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in pg_sql
    for marker in ('handoff_status', 'handoff_batch_id', 'handoff_result_json', 'processor_source_code'):
        assert marker in mysql_sql
        assert marker in pg_sql
    for marker in ('reviewed_by', 'reviewed_at', 'review_reason', 'published_at'):
        assert marker in mysql_sql
        assert marker in pg_sql
    for marker in ('scan_status', 'scan_message', 'scan_time', 'scanner_name', 'idx_knowledge_files_scan_status_time'):
        assert marker in mysql_sql
        assert marker in pg_sql
    for marker in ('attempt_count', 'lease_owner', 'lease_until', 'next_retry_at', 'idx_report_exports_dispatch'):
        assert marker in mysql_sql
        assert marker in pg_sql
    for marker in (
        'collection_lease_owner',
        'collection_lease_until',
        'handoff_lease_owner',
        'handoff_lease_until',
        'idx_data_sources_collection_lease',
        'idx_collection_runs_handoff_lease',
    ):
        assert marker in mysql_sql
        assert marker in pg_sql
    for marker in (
        'idx_generation_tasks_dispatch',
        'idx_generation_tasks_cancel_dispatch',
        'ck_generation_tasks_attempt_count',
        'cancel_requested_at',
    ):
        assert marker in mysql_sql
        assert marker in pg_sql
    assert "action IN ('approve', 'reject', 'withdraw', 'reprocess')" in mysql_sql
    assert "action IN ('approve', 'reject', 'withdraw', 'reprocess')" in pg_sql


def test_ruoyi_base_sql_contains_all_framework_tables() -> None:
    sql_dir = Path(__file__).parents[1] / 'sql'
    for filename in ('ruoyi-fastapi.sql', 'ruoyi-fastapi-pg.sql'):
        sql = (sql_dir / filename).read_text(encoding='utf-8')
        tables = set(re.findall(r'create\s+table\s+([a-z0-9_]+)', sql, flags=re.IGNORECASE))
        assert tables == BASELINE_RUOYI_TABLES
        assert not REMOVED_PLATFORM_TABLES.intersection(tables)


def test_built_in_roles_keep_the_portal_user_out_of_admin_menus() -> None:
    sql_dir = Path(__file__).parents[1] / 'sql'
    for filename in ('ruoyi-fastapi.sql', 'ruoyi-fastapi-pg.sql'):
        sql = (sql_dir / filename).read_text(encoding='utf-8')
        assert "'普通用户'" in sql
        assert "'普通角色'" not in sql
        assert 'sys_role_menu values (2,' not in sql
        assert "sys_role_menu values ('2'," not in sql


def test_full_system_orm_registers_foundation_and_domain_tables() -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLES
    assert len(APPLICATION_TABLES | FRAMEWORK_TABLES) == FULL_TABLE_COUNT
    assert not FRAMEWORK_TABLES & set(Base.metadata.tables)
    for table_name, table in Base.metadata.tables.items():
        expected = {'sys_user_role': ('user_id', 'role_id'), 'sys_role_menu': ('role_id', 'menu_id')}.get(
            table_name, ('id',)
        )
        assert tuple(table.primary_key.columns.keys()) == expected


def test_removed_organization_concepts_are_not_exposed_by_active_api_models() -> None:
    assert 'dept_id' not in UserModel.model_fields
    assert 'dept' not in UserInfoModel.model_fields
    assert 'post_ids' not in UserInfoModel.model_fields
    assert 'post_ids' not in UserDetailModel.model_fields
    assert 'posts' not in UserDetailModel.model_fields
    assert 'post_group' not in UserProfileModel.model_fields
    assert 'dept_check_strictly' not in RoleModel.model_fields
    assert 'dept_name' not in OnlineModel.model_fields


def unique_columns(table_name: str) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_critical_relations_and_unique_constraints_are_explicit() -> None:
    tables = Base.metadata.tables
    relations = {
        ('knowledge_files', 'user_id'): ('sys_user.id', 'RESTRICT'),
        ('reports', 'user_id'): ('sys_user.id', 'RESTRICT'),
        ('report_versions', 'report_id'): ('reports.id', 'CASCADE'),
        ('collection_runs', 'source_id'): ('data_sources.id', 'RESTRICT'),
        ('news_articles', 'category_id'): ('categories.id', 'RESTRICT'),
        ('papers', 'category_id'): ('categories.id', 'RESTRICT'),
        ('sys_job_log', 'job_id'): ('sys_job.id', 'SET NULL'),
        ('sys_dict_data', 'type_code'): ('sys_dict_type.code', 'CASCADE'),
    }
    for (table_name, column_name), expected in relations.items():
        foreign_keys = tables[table_name].c[column_name].foreign_keys
        assert expected in {(foreign_key.target_fullname, foreign_key.ondelete) for foreign_key in foreign_keys}
    assert ('username',) in unique_columns('sys_user')
    assert ('code',) in unique_columns('sys_role')
    assert ('key',) in unique_columns('sys_config')
    assert ('code',) in unique_columns('sys_dict_type')
    assert ('name', 'group_key') in unique_columns('sys_job')
    assert ('report_id', 'version') in unique_columns('report_versions')
    assert ('request_id',) in unique_columns('generation_tasks')
    assert ('id', 'report_id') in unique_columns('generation_tasks')
    assert ('request_id',) in unique_columns('collection_runs')
    assert ('id', 'source_id') in unique_columns('collection_runs')

    assets = tables['report_assets']
    composite = next(
        fk for fk in assets.foreign_key_constraints if tuple(fk.columns.keys()) == ('task_id', 'report_id')
    )
    assert tuple(fk.target_fullname for fk in composite.elements) == (
        'generation_tasks.id',
        'generation_tasks.report_id',
    )
    assert composite.ondelete == 'RESTRICT'
    runs = tables['collection_runs']
    retry_fk = next(fk for fk in runs.foreign_key_constraints if tuple(fk.columns.keys()) == ('parent_id', 'source_id'))
    assert tuple(fk.target_fullname for fk in retry_fk.elements) == ('collection_runs.id', 'collection_runs.source_id')
    assert retry_fk.ondelete == 'RESTRICT'

    tasks = tables['generation_tasks']
    assert {'report_id', 'materials', 'attempts', 'execution_token', 'lease_expires_at'} <= set(tasks.c.keys())
    assert not {'user_id', 'prompt_version_id', 'template_id', 'lease_owner', 'lease_until'} & set(tasks.c.keys())
    assert not {'reviewed_by', 'reviewed_at', 'review_reason'} & set(tables['news_articles'].c.keys())
    assert not {'content', 'content_zh'} & set(tables['papers'].c.keys())
    for table_name in ('news_articles', 'papers', 'collection_runs', 'data_sources'):
        assert not any(column.name.startswith('handoff_') for column in tables[table_name].c)
    assert not {'user_id', 'model_code', 'api_key'} & set(tables['ai_models'].c.keys())

    baskets = tables['basket_items']
    targets = {
        'article_id': 'news_articles.id',
        'paper_id': 'papers.id',
        'file_id': 'knowledge_files.id',
        'report_id': 'reports.id',
    }
    for target, reference in targets.items():
        assert next(iter(baskets.c[target].foreign_keys)).target_fullname == reference
        assert any(
            index.unique and tuple(index.columns.keys()) == ('user_id', 'action', target) for index in baskets.indexes
        )
    expected_checks = {
        'ck_roles_data_scope',
        'ck_knowledge_files_status',
        'ck_knowledge_files_version',
        'ck_basket_items_target',
        'ck_basket_items_action',
        'ck_generation_tasks_progress',
        'ck_generation_tasks_attempts',
        'ck_generation_tasks_status',
        'ck_report_assets_kind',
        'ck_report_assets_storage_key',
        'ck_collection_runs_counts',
        'ck_collection_runs_status',
        'ck_digest_schedules_frequency',
        'ck_categories_enabled_model',
    }
    actual_checks = {constraint.name for table in tables.values() for constraint in table.constraints}
    assert expected_checks <= actual_checks


def test_sqlite_enforces_real_job_fk_and_unique_job_identity(sqlite_schema: Engine) -> None:
    users, jobs, logs = (Base.metadata.tables[name] for name in ('sys_user', 'sys_job', 'sys_job_log'))
    job_values = {'name': 'offline-job', 'group_key': 'default', 'invoke_target': 'builtins.print'}
    log_values = {**job_values, 'executor': 'default'}
    with sqlite_schema.begin() as connection:
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(logs.insert().values(id=1, job_id=999, **log_values))
        connection.execute(
            users.insert().values(id=1, username='offline', nickname='Offline', sex='0', status='0', del_flag='0')
        )
        connection.execute(jobs.insert().values(id=1, **job_values))
        connection.execute(logs.insert().values(id=1, job_id=1, **log_values))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(jobs.insert().values(id=2, **job_values))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                users.insert().values(id=2, username='offline', nickname='Duplicate', sex='0', status='0', del_flag='0')
            )


def test_sqlite_generation_request_id_is_globally_unique(sqlite_schema: Engine) -> None:
    users, reports, tasks = (Base.metadata.tables[name] for name in ('sys_user', 'reports', 'generation_tasks'))
    with sqlite_schema.begin() as connection:
        for identity in (1, 2):
            connection.execute(
                users.insert().values(
                    id=identity, username=f'offline-{identity}', nickname='Offline', sex='0', status='0', del_flag='0'
                )
            )
            connection.execute(
                reports.insert().values(id=identity, user_id=identity, title='Offline', type='research')
            )
        connection.execute(tasks.insert().values(id=3, report_id=1, request_id='same-request'))
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(tasks.insert().values(id=4, report_id=2, request_id='same-request'))
        # The same PK/FK pair is otherwise valid: only the shared request ID
        # must reject a second user's task, not an unrelated integrity error.
        connection.execute(tasks.insert().values(id=4, report_id=2, request_id='different-request'))
        assert connection.execute(select(tasks.c.id, tasks.c.request_id).order_by(tasks.c.id)).all() == [
            (3, 'same-request'), (4, 'different-request')
        ]
