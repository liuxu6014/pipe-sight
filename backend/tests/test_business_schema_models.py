"""Business ORM repair: offline DDL, exact columns, guards and existing catalog names."""

import re
import socket
import sqlite3

import pytest
from sqlalchemy import CheckConstraint, Identity, UniqueConstraint
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable

from app.business_ids import BUSINESS_ID_TABLES, MAX_BIGINT
from app.infrastructure.models.registry import register_sqlalchemy_models
from app.schema_contract import load_contract
from config.database import Base

register_sqlalchemy_models()
BUSINESS_TABLES = {*BUSINESS_ID_TABLES, 'ai_models', 'basket_items', 'report_versions'}
BUSINESS_COLUMN_COUNT = 196
MISSING_DEFAULT_COUNT = 33
MISSING_DEFAULTS = {
    'ai_models': ('parameters', 'created_at', 'updated_at'),
    'basket_items': ('created_at',),
    'categories': ('created_at', 'updated_at'),
    'collection_runs': ('updated_at',),
    'data_sources': ('updated_at',),
    'digest_schedules': ('timezone', 'generation_config', 'created_at', 'updated_at'),
    'generation_tasks': ('config_snapshot', 'materials', 'created_at', 'updated_at'),
    'knowledge_files': ('created_at', 'updated_at'),
    'model_calls': ('created_at',),
    'news_articles': ('created_at', 'updated_at'),
    'papers': ('created_at', 'updated_at'),
    'report_assets': ('config_snapshot', 'created_at', 'updated_at'),
    'report_versions': ('created_at',),
    'reports': ('created_at', 'updated_at'),
    'templates': ('sections', 'image_config', 'created_at', 'updated_at'),
}
CATALOG_INDEX_NAMES = {
    'ai_models': set(),
    'basket_items': {f'uk_basket_items_{key}_id' for key in ('article', 'paper', 'file', 'report')},
    'categories': {'uk_categories_name'},
    'collection_runs': {
        'idx_collection_runs_lease',
        'idx_collection_runs_source_id',
        'idx_collection_runs_status',
        'uk_collection_runs_active',
        'uk_collection_runs_parent_id',
        'uk_collection_runs_request_id',
        'uk_collection_runs_id_source_id',
    },
    'data_sources': {'idx_data_sources_next_run_at'},
    'digest_schedules': {'idx_digest_schedules_next_run_at'},
    'generation_tasks': {
        'idx_generation_tasks_lease',
        'idx_generation_tasks_report_id',
        'idx_generation_tasks_status',
        'idx_generation_tasks_schedule_id',
        'uk_generation_tasks_request_id',
        'uk_generation_tasks_id_report_id',
    },
    'knowledge_files': {'idx_knowledge_files_user_id', 'idx_knowledge_files_status_updated_at'},
    'model_calls': {'idx_model_calls_model_id_created_at', 'idx_model_calls_task_id_created_at'},
    'news_articles': {
        'idx_news_articles_category_id',
        'idx_news_articles_source_id',
        'idx_news_articles_published_at',
        'uk_news_articles_url',
    },
    'papers': {'idx_papers_category_id', 'uk_papers_doi', 'uk_papers_url', 'idx_papers_date'},
    'report_assets': {'idx_report_assets_report_id'},
    'report_versions': {'uk_report_versions_report_id_version'},
    'reports': {'idx_reports_user_id'},
    'templates': set(),
}


@pytest.fixture(autouse=True)
def no_external_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('Business schema model tests must stay offline')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)


def test_exact_193_column_types_nullability_and_names_are_preserved() -> None:
    contract = load_contract()
    tables = {row['name']: row for row in [*contract['tables'], *contract['optional_table_definitions']]}
    count = 0
    for name in BUSINESS_TABLES:
        table = Base.metadata.tables[name]
        expected = tables[name]['columns']
        assert set(table.c.keys()) == {column['name'] for column in expected}
        for column in expected:
            actual = table.c[column['name']]
            kind = {'时间': 'timestamp with time zone', 'time': 'time without time zone'}.get(
                column['type'], column['type']
            )
            assert str(actual.type.compile(dialect=postgresql.dialect())).lower() == kind
            assert actual.nullable == column['nullable']
            count += 1
    assert count == BUSINESS_COLUMN_COUNT


def test_all_33_missing_defaults_added_without_dropping_client_defaults() -> None:
    assert sum(map(len, MISSING_DEFAULTS.values())) == MISSING_DEFAULT_COUNT
    for table, names in MISSING_DEFAULTS.items():
        for name in names:
            column = Base.metadata.tables[table].c[name]
            assert column.server_default is not None
            assert column.default is not None
            value = str(column.server_default.arg)
            if name in {'created_at', 'updated_at'}:
                assert value == "date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')"
            elif name == 'timezone':
                assert value == 'Asia/Shanghai'
            else:
                assert value == ("'[]'" if name in {'sections', 'materials'} else "'{}'")
    available = Base.metadata.tables['collection_runs'].c.available_at
    assert available.server_default is None and available.default is not None


def test_three_existing_identities_and_twelve_shared_sequence_defaults() -> None:
    for name in ('ai_models', 'basket_items', 'report_versions'):
        identity = Base.metadata.tables[name].c.id.identity
        assert isinstance(identity, Identity) and not identity.always
        assert (identity.start, identity.increment, identity.minvalue, identity.maxvalue) == (1, 1, 1, MAX_BIGINT)
        assert identity.cache == 1 and not identity.cycle
    for name in BUSINESS_ID_TABLES:
        column = Base.metadata.tables[name].c.id
        assert column.identity is None and column.default.name == 'business_id_seq'
        assert 'business_id_seq' in str(CreateTable(column.table).compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize('table_name', sorted(BUSINESS_TABLES))
def test_index_names_are_existing_catalog_names_plus_only_two_new_queries(table_name: str) -> None:
    table = Base.metadata.tables[table_name]
    names = {index.name for index in table.indexes} | {
        constraint.name for constraint in table.constraints if isinstance(constraint, UniqueConstraint)
    }
    assert names == CATALOG_INDEX_NAMES[table_name]


def test_desc_partial_predicates_and_paper_date_expression() -> None:
    ddl = {
        index.name: str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        for name in BUSINESS_TABLES
        for index in Base.metadata.tables[name].indexes
    }
    for name, column in (
        ('idx_collection_runs_source_id', 'created_at'),
        ('idx_reports_user_id', 'updated_at'),
        ('idx_knowledge_files_user_id', 'updated_at'),
        ('idx_news_articles_source_id', 'published_at'),
    ):
        assert f'{column} DESC' in ddl[name]
    assert 'WHERE lease_expires_at IS NOT NULL' in ddl['idx_generation_tasks_lease']
    assert "WHERE status IN ('queued','running','stopping')" in ddl['uk_collection_runs_active']
    assert "WHERE status IN ('running','stopping')" in ddl['idx_collection_runs_lease']
    assert 'WHERE is_enabled' in ddl['idx_digest_schedules_next_run_at']
    assert 'doi IS NULL AND url IS NOT NULL' in ddl['uk_papers_url']
    for name in ('idx_papers_category_id', 'idx_papers_date'):
        assert "rpad(published_date, 10, '-01') DESC, id" in ddl[name]


def test_canonical_check_names_and_preserved_collection_state_guards() -> None:
    for name in BUSINESS_TABLES:
        for check in Base.metadata.tables[name].constraints:
            if isinstance(check, CheckConstraint):
                assert check.name.startswith(f'ck_{name}_')
                assert not re.fullmatch(r'ck_.*_\d+', check.name)
    checks = {check.name for check in Base.metadata.tables['collection_runs'].constraints}
    assert {
        f'ck_collection_runs_{key}'
        for key in (
            'request_id',
            'parent_trigger',
            'parent_id',
            'counts',
            'success',
            'error',
            'queued',
            'active',
            'running',
            'stop',
            'lease_pair',
            'terminal',
            'times',
            'json',
        )
    } <= checks


@pytest.mark.parametrize(
    'table_name,check_name,good,bad',
    [
        (
            'news_articles',
            'title_url',
            {'title': '真实标题', 'url': 'https://example.invalid'},
            {'title': ' ', 'url': ' '},
        ),
        ('papers', 'title', {'title': '论文标题'}, {'title': ' '}),
        ('papers', 'source_link', {'doi': '10.1/test', 'url': None}, {'doi': ' ', 'url': ' '}),
        ('categories', 'name_prompt', {'name': '类别', 'prompt': '实际提示词'}, {'name': ' ', 'prompt': ' '}),
        ('templates', 'name_prompt', {'name': '模板', 'prompt': '实际提示词'}, {'name': ' ', 'prompt': ' '}),
        ('reports', 'title', {'title': '实际成果'}, {'title': ' '}),
        ('report_assets', 'mime_type', {'mime_type': 'image/png'}, {'mime_type': ' '}),
    ],
)
def test_nonblank_guards_reject_invalid_rows(
    table_name: str, check_name: str, good: dict[str, str | None], bad: dict[str, str | None]
) -> None:
    check = next(c for c in Base.metadata.tables[table_name].constraints if c.name == f'ck_{table_name}_{check_name}')
    # Execute the actual ORM predicate in isolated SQLite; no production connection.
    with sqlite3.connect(':memory:') as connection:
        connection.execute(f'CREATE TABLE guard ({", ".join(key + " TEXT" for key in good)}, CHECK ({check.sqltext}))')
        statement = f'INSERT INTO guard VALUES ({", ".join("?" for _ in good)})'
        connection.execute(statement, tuple(good.values()))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, tuple(bad.values()))


def test_real_partial_date_validation_is_postgresql_only_and_history_json_shapes_exist() -> None:
    paper = Base.metadata.tables['papers']
    pg_ddl = str(CreateTable(paper).compile(dialect=postgresql.dialect()))
    assert 'make_date(' in pg_ddl and 'substring(published_date' in pg_ddl
    assert '^[0-9]{4}(-[0-9]{2}){0,2}$' in pg_ddl
    assert 'make_date(' not in str(CreateTable(paper).compile(dialect=sqlite.dialect()))
    history = str(CreateTable(Base.metadata.tables['report_versions']).compile(dialect=postgresql.dialect()))
    for key, shape in (
        ('sections', 'array'),
        ('citations', 'array'),
        ('quality_issues', 'array'),
        ('model_snapshot', 'object'),
    ):
        assert f"jsonb_typeof({key})='{shape}'" in history
