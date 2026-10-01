import re
from pathlib import Path

from sqlalchemy import create_engine, inspect

import module_admin.entity.do.config_do
import module_admin.entity.do.dept_do
import module_admin.entity.do.dict_do
import module_admin.entity.do.job_do
import module_admin.entity.do.log_do
import module_admin.entity.do.menu_do
import module_admin.entity.do.notice_do
import module_admin.entity.do.post_do
import module_admin.entity.do.role_do
import module_admin.entity.do.user_do  # noqa: F401
import module_ai.entity.do.ai_chat_do
import module_ai.entity.do.ai_model_do  # noqa: F401
import module_generator.entity.do.gen_do  # noqa: F401
import module_pipeline.entity.do.pipeline_do  # noqa: F401
from config.database import Base
from module_admin.entity.vo.online_vo import OnlineModel
from module_admin.entity.vo.role_vo import RoleModel
from module_admin.entity.vo.user_vo import UserDetailModel, UserInfoModel, UserModel, UserProfileModel

CORE_TABLES = {
    'knowledge_files',
    'user_saved_items',
    'generation_tasks',
    'reports',
    'report_versions',
    'pipeline_prompt_versions',
    'pipeline_template_versions',
}
COLLECTION_TABLES = {
    'data_sources',
    'collection_runs',
    'news_articles',
    'papers',
}
DOMAIN_TABLES = CORE_TABLES | COLLECTION_TABLES
FULL_TABLE_COUNT = 25
DEFERRED_TABLES = {
    'collection_records',
    'taxonomy_terms',
    'resource_terms',
    'knowledge_chunks',
    'report_templates',
    'prompt_versions',
    'generation_task_items',
    'report_citations',
    'report_exports',
}
OBSOLETE_GENERIC_TABLES = {
    'contents',
    'chunks',
    'model_calls',
    'audit_logs',
    'sources',
    'crawl_tasks',
    'articles',
}
RUOYI_TABLES = {
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
REMOVED_PLATFORM_TABLES = {
    'sys_dept',
    'sys_post',
    'sys_role_dept',
    'sys_user_post',
    'sys_notice',
    'gen_table',
    'gen_table_column',
}


def test_domain_models_are_registered_and_sqlite_compatible() -> None:
    assert DOMAIN_TABLES.issubset(Base.metadata.tables)
    assert RUOYI_TABLES.issubset(Base.metadata.tables)
    assert not OBSOLETE_GENERIC_TABLES.intersection(Base.metadata.tables)
    assert not DEFERRED_TABLES.intersection(Base.metadata.tables)
    assert not REMOVED_PLATFORM_TABLES.intersection(Base.metadata.tables)

    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)

    assert DOMAIN_TABLES.issubset(inspect(engine).get_table_names())


def test_mysql_and_postgresql_domain_sql_have_the_same_table_set() -> None:
    sql_dir = Path(__file__).parents[1] / 'sql'
    mysql_sql = (sql_dir / 'pipeline-domain.sql').read_text(encoding='utf-8') + (
        sql_dir / 'pipeline-domain-enhancement.sql'
    ).read_text(encoding='utf-8')
    pg_sql = (sql_dir / 'pipeline-domain-pg.sql').read_text(encoding='utf-8') + (
        sql_dir / 'pipeline-domain-enhancement-pg.sql'
    ).read_text(encoding='utf-8')
    for table_name in DOMAIN_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' in pg_sql
    for table_name in OBSOLETE_GENERIC_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in pg_sql
    for table_name in DEFERRED_TABLES:
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in mysql_sql
        assert f'CREATE TABLE IF NOT EXISTS {table_name}' not in pg_sql
    for marker in ('handoff_status', 'handoff_batch_id', 'handoff_result_json', 'processor_source_code'):
        assert marker in mysql_sql
        assert marker in pg_sql


def test_ruoyi_base_sql_contains_all_framework_tables() -> None:
    sql_dir = Path(__file__).parents[1] / 'sql'
    for filename in ('ruoyi-fastapi.sql', 'ruoyi-fastapi-pg.sql'):
        sql = (sql_dir / filename).read_text(encoding='utf-8')
        tables = set(re.findall(r'create\s+table\s+([a-z0-9_]+)', sql, flags=re.IGNORECASE))
        assert RUOYI_TABLES.issubset(tables)
        assert not REMOVED_PLATFORM_TABLES.intersection(tables)


def test_built_in_roles_keep_the_portal_user_out_of_admin_menus() -> None:
    sql_dir = Path(__file__).parents[1] / 'sql'
    for filename in ('ruoyi-fastapi.sql', 'ruoyi-fastapi-pg.sql'):
        sql = (sql_dir / filename).read_text(encoding='utf-8')
        assert "'普通用户'" in sql
        assert "'普通角色'" not in sql
        assert 'sys_role_menu values (2,' not in sql
        assert "sys_role_menu values ('2'," not in sql


def test_full_system_orm_registers_ruoyi_and_domain_tables() -> None:
    assert RUOYI_TABLES.issubset(Base.metadata.tables)
    assert DOMAIN_TABLES.issubset(Base.metadata.tables)
    assert len(RUOYI_TABLES | DOMAIN_TABLES) == FULL_TABLE_COUNT
    assert len(Base.metadata.tables) == FULL_TABLE_COUNT
    assert not REMOVED_PLATFORM_TABLES.intersection(Base.metadata.tables)


def test_removed_organization_concepts_are_not_exposed_by_active_api_models() -> None:
    assert 'dept_id' not in UserModel.model_fields
    assert 'dept' not in UserInfoModel.model_fields
    assert 'post_ids' not in UserInfoModel.model_fields
    assert 'post_ids' not in UserDetailModel.model_fields
    assert 'posts' not in UserDetailModel.model_fields
    assert 'post_group' not in UserProfileModel.model_fields
    assert 'dept_check_strictly' not in RoleModel.model_fields
    assert 'dept_name' not in OnlineModel.model_fields


def test_critical_relations_and_unique_constraints_are_explicit() -> None:
    saved_items = Base.metadata.tables['user_saved_items']
    saved_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in saved_items.constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    }
    assert ('user_id', 'item_type', 'item_id', 'action') in saved_unique_columns

    job_primary_key = tuple(column.name for column in Base.metadata.tables['sys_job'].primary_key.columns)
    assert job_primary_key == ('job_id',)

    report_versions = Base.metadata.tables['report_versions']
    assert any(
        foreign_key.target_fullname == 'reports.report_id' for foreign_key in report_versions.c.report_id.foreign_keys
    )

    collection_runs = Base.metadata.tables['collection_runs']
    source_foreign_key = next(iter(collection_runs.c.source_id.foreign_keys))
    assert source_foreign_key.ondelete == 'RESTRICT'

    assert tuple(Base.metadata.tables['knowledge_files'].primary_key.columns.keys()) == ('file_id',)
    assert tuple(Base.metadata.tables['user_saved_items'].primary_key.columns.keys()) == ('saved_item_id',)
    assert tuple(Base.metadata.tables['generation_tasks'].primary_key.columns.keys()) == ('task_id',)
    assert 'report_id' not in Base.metadata.tables['generation_tasks'].columns
    assert 'prompt_version_id' not in Base.metadata.tables['generation_tasks'].columns
    assert not Base.metadata.tables['generation_tasks'].c.template_id.foreign_keys
    assert 'source_task_id' in Base.metadata.tables['reports'].columns

    for table_name in ('news_articles', 'papers'):
        table = Base.metadata.tables[table_name]
        assert {
            'handoff_status',
            'handoff_batch_id',
            'handoff_record_id',
            'handoff_trace_id',
            'handoff_version',
            'handoff_result_json',
            'handoff_time',
            'handoff_error',
        }.issubset(table.columns.keys())

    assert {
        'handoff_status',
        'handoff_batch_id',
        'handoff_count',
        'handoff_processed_count',
        'handoff_failed_count',
    }.issubset(Base.metadata.tables['collection_runs'].columns.keys())
    assert {'handoff_mode', 'processor_source_code'}.issubset(Base.metadata.tables['data_sources'].columns.keys())

    ai_model_unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in Base.metadata.tables['ai_models'].constraints
        if constraint.__class__.__name__ == 'UniqueConstraint'
    }
    assert ('user_id', 'provider', 'model_code') in ai_model_unique_columns
    assert not Base.metadata.tables['ai_models'].c.user_id.nullable
    assert 'dept_id' not in Base.metadata.tables['sys_user'].columns
    assert 'dept_name' not in Base.metadata.tables['sys_oper_log'].columns
    assert 'dept_check_strictly' not in Base.metadata.tables['sys_role'].columns
    assert 'dept_id' not in Base.metadata.tables['ai_models'].columns
    assert 'dept_id' not in Base.metadata.tables['knowledge_files'].columns

    expected_checks = {
        'ck_sys_role_data_scope',
        'ck_knowledge_files_permission_scope',
        'ck_user_saved_items_item_type',
        'ck_generation_tasks_progress',
        'ck_news_articles_relevance',
        'ck_data_sources_handoff_mode',
        'ck_collection_runs_handoff_status',
        'ck_news_articles_handoff_status',
        'ck_papers_handoff_status',
    }
    actual_checks = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if constraint.__class__.__name__ == 'CheckConstraint'
    }
    assert expected_checks.issubset(actual_checks)
