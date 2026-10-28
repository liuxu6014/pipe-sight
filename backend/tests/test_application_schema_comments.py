"""Canonical 29-table/340-column comments across metadata, SQL and migration DDL."""

# Literal counts and limits are independent assertions of the approved schema.
# ruff: noqa: PLR2004

import ast
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from sqlalchemy import JSON, Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import SetColumnComment, SetTableComment

from app import ruoyi_table_names, schema_comments_v1, schema_comments_v2, schema_comments_v3
from app import schema_comment_runtime as schema_migration
from app import schema_migration as historical_migration
from app.infrastructure.models.registry import apply_metadata_comments, register_sqlalchemy_models
from app.schema_comment_runtime import apply_schema_comments, render_comment_sql
from app.schema_comments import (
    COLUMN_COMMENTS,
    FRAMEWORK_TABLE_NAMES,
    OPTIONAL_TABLE_NAMES,
    TABLE_COMMENTS,
    VIEW_COMMENTS,
)
from app.schema_contract import load_contract
from app.schema_migration import fingerprint
from config.database import Base

register_sqlalchemy_models()

SQL_PATH = Path(__file__).parents[1] / 'sql/application-comments-pg.sql'
PUBLIC_TABLES = set(TABLE_COMMENTS)
MODEL_TABLES = PUBLIC_TABLES - set(FRAMEWORK_TABLE_NAMES)
GUARDED_OBJECTS = set(OPTIONAL_TABLE_NAMES) | set(FRAMEWORK_TABLE_NAMES) | set(VIEW_COMMENTS)
COMMENT_RE = re.compile(
    r'COMMENT ON (?P<kind>TABLE|VIEW|COLUMN) public\."(?P<table>[a-z_][a-z_0-9]*)"'
    r'(?:\."(?P<column>[a-z_][a-z_0-9]*)")? IS \'(?P<comment>(?:[^\']|\'\')*)\';'
)
OPTIONAL_BLOCK_RE = re.compile(
    r"DO \$pipesight_(?P<table>[a-z_0-9]+)_comments\$\s*BEGIN\s*"
    r"IF to_regclass\('public\.(?P=table)'\) IS NOT NULL THEN\s*"
    r"(?P<body>.*?)\s*END IF;\s*END;\s*\$pipesight_(?P=table)_comments\$;",
    re.DOTALL,
)


def _comments(sql: str) -> dict:
    matches = list(COMMENT_RE.finditer(sql))
    keys = [(m['kind'], m['table'], m['column']) for m in matches]
    assert all(count == 1 for count in Counter(keys).values()), '重复COMMENT语句'
    return {key: m['comment'].replace("''", "'") for key, m in zip(keys, matches, strict=True)}


def _expected(names: set[str]) -> dict:
    result = {('TABLE', n, None): TABLE_COMMENTS[n] for n in names}
    result.update({('COLUMN', n, c): text for n in names for c, text in COLUMN_COMMENTS[n].items()})
    return result


def test_comment_data_matches_frozen_317_fields_plus_23_optional_fields() -> None:
    baseline = {t['name']: {c['name'] for c in t['columns']} for t in load_contract()['tables']}
    assert len(baseline) == 27 and sum(map(len, baseline.values())) == 320
    assert set(baseline) | set(OPTIONAL_TABLE_NAMES) == PUBLIC_TABLES
    assert sum(len(COLUMN_COMMENTS[n]) for n in OPTIONAL_TABLE_NAMES) == 23
    assert sum(map(len, COLUMN_COMMENTS.values())) == 343
    for name, fields in baseline.items():
        assert set(COLUMN_COMMENTS[name]) == fields
    source = Path(__file__).parents[1] / 'src/app/schema_comments.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    assert all(isinstance(n, (ast.Expr, ast.Assign, ast.AnnAssign)) for n in tree.body)


def test_all_29_tables_and_340_columns_have_specific_chinese_comments() -> None:
    assert len(PUBLIC_TABLES) == 29
    assert set(Base.metadata.tables) == MODEL_TABLES and len(MODEL_TABLES) == 27
    assert sum(len(t.c) for t in Base.metadata.tables.values()) == 339
    placeholders = {'字段说明', '表说明', '待补充', 'TODO', 'TBD', '主键', '创建时间', '更新时间'}
    for name, table_comment in TABLE_COMMENTS.items():
        for label, comment in [(name, table_comment), *COLUMN_COMMENTS[name].items()]:
            assert isinstance(comment, str) and comment == comment.strip() and comment, (name, label)
            assert comment not in placeholders and re.search(r'[\u4e00-\u9fff]', comment), (name, label)
            assert len(comment) > 6, (name, label)
    for table in Base.metadata.tables.values():
        assert table.comment == TABLE_COMMENTS[table.name]
        assert {c.name: c.comment for c in table.c} == COLUMN_COMMENTS[table.name]
        for column in table.c:
            if isinstance(column.type, JSON):
                assert 'JSON' in column.comment, f'{table.name}.{column.name}'


def test_registry_normalizes_existing_comments_and_is_idempotent() -> None:
    metadata = MetaData()
    copy = Base.metadata.tables['sys_user'].to_metadata(metadata)
    copy.comment = '旧表说明'
    copy.c.password_hash.comment = None
    apply_metadata_comments(metadata)
    assert copy.comment == TABLE_COMMENTS['sys_user']
    assert copy.c.password_hash.comment == COLUMN_COMMENTS['sys_user']['password_hash']
    apply_metadata_comments(metadata)
    assert {c.name: c.comment for c in copy.c} == COLUMN_COMMENTS['sys_user']


def test_registry_rejects_uncontracted_columns_before_partial_annotation() -> None:
    metadata = MetaData()
    users = Base.metadata.tables['sys_user'].to_metadata(metadata)
    users.comment = '全量预检前保留原注释'
    Table('unapproved', metadata, Column('id', String))
    with pytest.raises(ValueError, match='中文注释契约'):
        apply_metadata_comments(metadata)
    assert users.comment == '全量预检前保留原注释'


def test_generated_sql_exactly_matches_data_and_registered_orm_comments() -> None:
    sql = SQL_PATH.read_text(encoding='utf-8')
    assert sql == render_comment_sql()
    actual = _comments(sql)
    expected = _expected(PUBLIC_TABLES)
    for name, view in VIEW_COMMENTS.items():
        expected['VIEW', name, None] = view['comment']
        expected.update({('COLUMN', name, c): text for c, text in view['columns'].items()})
    assert actual == expected
    assert len([key for key in actual if key[0] == 'TABLE']) == 29
    assert len([key for key in actual if key[0] == 'COLUMN' and key[1] in PUBLIC_TABLES]) == 343
    for table in Base.metadata.tables.values():
        assert actual['TABLE', table.name, None] == table.comment
        for col in table.c:
            assert actual['COLUMN', table.name, col.name] == col.comment


def test_optional_framework_and_catalog_objects_are_individually_guarded() -> None:
    sql = SQL_PATH.read_text(encoding='utf-8')
    blocks = list(OPTIONAL_BLOCK_RE.finditer(sql))
    assert Counter(b['table'] for b in blocks) == Counter(dict.fromkeys(GUARDED_OBJECTS, 1))
    for block in blocks:
        name = block['table']
        if name in TABLE_COMMENTS:
            expected = _expected({name})
        else:
            view = VIEW_COMMENTS[name]
            expected = {('VIEW', name, None): view['comment']}
            expected.update({('COLUMN', name, c): text for c, text in view['columns'].items()})
        assert _comments(block['body']) == expected
        assert not COMMENT_RE.sub('', block['body']).strip()
    core = OPTIONAL_BLOCK_RE.sub('', sql)
    assert {key[1] for key in _comments(core)} == PUBLIC_TABLES - GUARDED_OBJECTS


def test_sql_has_only_comments_and_guarded_optional_blocks() -> None:
    sql = re.sub(r'^\s*--[^\n]*$', '', SQL_PATH.read_text(encoding='utf-8'), flags=re.MULTILINE)
    assert not COMMENT_RE.sub('', OPTIONAL_BLOCK_RE.sub('', sql)).strip()


def test_runtime_comment_commands_are_single_prepared_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    inspector = SimpleNamespace(
        get_columns=lambda name, **kwargs: [{'name': column} for column in COLUMN_COMMENTS[name]],
        get_view_names=lambda **kwargs: list(VIEW_COMMENTS),
    )
    bind = SimpleNamespace(in_transaction=lambda: True, begin_nested=nullcontext, exec_driver_sql=Mock())
    monkeypatch.setattr(schema_migration, 'assert_rehearsal', lambda *args, **kwargs: None)
    monkeypatch.setattr(schema_migration, '_inventory', lambda *args: {'public.' + name for name in PUBLIC_TABLES})
    monkeypatch.setattr(schema_migration.sa, 'inspect', lambda *args: inspector)
    monkeypatch.setattr(schema_migration, 'verify_schema_comments', lambda *args, **kwargs: {'verified': True})
    assert apply_schema_comments(bind) == {'verified': True}
    commands = [call.args[0] for call in bind.exec_driver_sql.call_args_list]
    assert len(commands) == len(_comments(render_comment_sql()))
    assert all(COMMENT_RE.fullmatch(command) for command in commands)


def test_migration_metadata_and_compiled_ddl_use_canonical_comments() -> None:
    metadata = Base.metadata
    statements = _comments(SQL_PATH.read_text(encoding='utf-8'))
    for table in metadata.tables.values():
        assert table.comment == TABLE_COMMENTS[table.name]
        assert {c.name: c.comment for c in table.c} == COLUMN_COMMENTS[table.name]
        assert TABLE_COMMENTS[table.name] in str(SetTableComment(table).compile(dialect=postgresql.dialect()))
        for column in table.c:
            ddl = str(SetColumnComment(column).compile(dialect=postgresql.dialect()))
            assert statements['COLUMN', table.name, column.name].replace("'", "''") in ddl


def test_historical_v1_comments_and_ddl_are_frozen_independently_of_runtime_v2() -> None:
    data = [schema_comments_v1.TABLE_COMMENTS, schema_comments_v1.COLUMN_COMMENTS, schema_comments_v1.VIEW_COMMENTS]
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == 'c5ead2912a8f0381eb411ff328b0a362ea181b68cb8c157335114bc4e6f2b5a4'
    assert historical_migration.TABLE_COMMENTS is schema_comments_v1.TABLE_COMMENTS
    assert historical_migration.COLUMN_COMMENTS is schema_comments_v1.COLUMN_COMMENTS
    assert 'users' in schema_comments_v1.TABLE_COMMENTS and 'sys_user' not in schema_comments_v1.TABLE_COMMENTS
    assert 'sys_user' in TABLE_COMMENTS and 'users' not in TABLE_COMMENTS
    metadata = historical_migration.target_metadata(optional_tables=OPTIONAL_TABLE_NAMES)
    for table in metadata.tables.values():
        assert table.comment == schema_comments_v1.TABLE_COMMENTS[table.name]
        assert {column.name: column.comment for column in table.c} == schema_comments_v1.COLUMN_COMMENTS[table.name]
    assert 'COMMENT ON TABLE public."users"' in historical_migration.render_comment_sql()
    assert 'COMMENT ON TABLE public."sys_user"' in render_comment_sql()


def test_ruoyi_name_revision_uses_frozen_v2_comments_not_numeric_runtime_comments() -> None:
    data = [schema_comments_v2.TABLE_COMMENTS, schema_comments_v2.COLUMN_COMMENTS, schema_comments_v2.VIEW_COMMENTS]
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == '6dfa82e96f5cfcc33af44bec583975d5f7e3bd769aff3e15b4df4f8ee812b9d9'
    assert ruoyi_table_names.COLUMN_COMMENTS is schema_comments_v2.COLUMN_COMMENTS
    assert ruoyi_table_names.TABLE_COMMENTS is schema_comments_v2.TABLE_COMMENTS
    assert ruoyi_table_names.COLUMN_COMMENTS is not COLUMN_COMMENTS
    assert 'business_id_seq' not in schema_comments_v2.COLUMN_COMMENTS['news_articles']['id']
    assert 'BIGINT' in COLUMN_COMMENTS['news_articles']['id']


def test_v3_comment_snapshot_is_frozen_independently_of_v4_semantic_policy() -> None:
    data = [schema_comments_v3.TABLE_COMMENTS, schema_comments_v3.COLUMN_COMMENTS, schema_comments_v3.VIEW_COMMENTS]
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert digest == '6f9beed5e8e895b6729214ac23546f1a26c3609136e5856d2f07dad82700b8fd'
    assert schema_comments_v3.COLUMN_COMMENTS is not COLUMN_COMMENTS
    assert schema_comments_v3.TABLE_COMMENTS == TABLE_COMMENTS
    assert schema_comments_v3.VIEW_COMMENTS == VIEW_COMMENTS
    expected = {name: set(cols) for name, cols in schema_comments_v3.COLUMN_COMMENTS.items()}
    expected['digest_schedules'] |= {'last_run_at', 'last_status', 'last_error'}
    assert expected == {name: set(cols) for name, cols in COLUMN_COMMENTS.items()}


def test_runtime_comments_distinguish_opaque_tokens_semantic_json_and_system_keys() -> None:
    c = COLUMN_COMMENTS
    for name in ('generation_tasks', 'collection_runs'):
        assert '普通' in c[name]['request_id'] and '原样保留' in c[name]['request_id']
        assert '系统' in c[name]['request_id'] and '映射' in c[name]['request_id']
        assert '编号数值化不改写' not in c[name]['request_id']
        assert '保留原业务字符串' in c[name]['execution_token']
    assert all(word in c['generation_tasks']['materials'] for word in ('type', '十进制字符串', '歧义', '正文'))
    assert '历史业务字符串原样保留' not in c['generation_tasks']['materials']
    assert all(word in c['generation_tasks']['config_snapshot'] for word in ('request_fingerprint', '重新计算', 'materials'))
    assert 'retry:父运行ID' in c['collection_runs']['request_id']
    assert '采集来源' in c['report_versions']['citations']
    assert 'compact-' + load_contract()['runtime_version'] in render_comment_sql()


def test_v5_only_business_audit_comments_change_from_frozen_v4() -> None:
    contract = load_contract()
    fields = {tuple(field) for field in contract['audit_timestamp_policy']['fields']}
    frozen_path = Path(__file__).parents[1] / 'data/schema/business-v4.json'
    frozen_business = json.loads(frozen_path.read_text(encoding='utf-8'))['catalog']
    changed = set()
    for name, table in frozen_business.items():
        for column in table['columns']:
            key = (name, column['name'])
            current = COLUMN_COMMENTS[name][column['name']]
            if current != column['comment']:
                changed.add(key)
            if key in fields:
                assert all(word in current for word in (
                    '北京时间', 'Asia/Shanghai', 'timestamp(0)', '无时区', '精度到秒', 'YYYY-MM-DD HH:mm:ss',
                )), key
                assert '带时区' not in current and 'UTC写入' not in current, key
            else:
                assert current == column['comment'], key
    assert changed == fields and len(changed) == 27
    for name in COLUMN_COMMENTS.keys() - frozen_business.keys():
        assert COLUMN_COMMENTS[name] == schema_comments_v3.COLUMN_COMMENTS[name]


def test_runtime_comments_document_numeric_pk_fk_and_unchanged_string_payloads() -> None:
    contract = load_contract()
    for name in contract['business_id_policy']['tables']:
        text = COLUMN_COMMENTS[name]['id']
        assert all(value in text for value in ('BIGINT', 'business_id_seq', '十进制字符串'))
    for fk in contract['foreign_keys'] + contract['optional_foreign_keys']:
        if fk['target'] in contract['business_id_policy']['tables']:
            for col in fk['columns']:
                assert 'BIGINT' in COLUMN_COMMENTS[fk['table']][col]
    for name in ('generation_tasks', 'collection_runs'):
        assert 'varchar(64)' in COLUMN_COMMENTS[name]['execution_token']
        assert 'varchar(128)' in COLUMN_COMMENTS[name]['request_id']


def test_status_password_units_dates_and_json_snapshot_semantics() -> None:
    c = COLUMN_COMMENTS
    assert 'bcrypt' in c['sys_user']['password_hash']
    assert '毫秒' in c['sys_oper_log']['duration_ms'] and '毫秒' in c['model_calls']['duration_ms']
    assert '字节' in c['knowledge_files']['size']
    assert '0至100' in c['generation_tasks']['progress']
    assert '原文发布时间' in c['news_articles']['published_at'] and '旧published_time' in c['news_articles']['published_at']
    assert all(v in c['papers']['published_date'] for v in ('YYYY', 'YYYY-MM', 'YYYY-MM-DD', '精度'))
    assert 'timestamp(0)' in c['sys_user']['created_at'] and '无时区' in c['sys_user']['created_at']
    assert '不覆盖' in c['knowledge_files']['extracted_text']
    assert 'NULL' in c['knowledge_files']['edited_text'] and '空字符串' in c['knowledge_files']['edited_text']
    assert '50' in c['generation_tasks']['materials'] and 'JSON' in c['generation_tasks']['materials']
    assert '输入不等于图片生成' in c['ai_models']['capabilities']
    for table, col, values in [
        ('generation_tasks', 'status', ('queued', 'running', 'completed', 'failed', 'cancelled')),
        ('collection_runs', 'status', ('queued', 'running', 'stopping', 'success', 'failed', 'cancelled')),
        ('knowledge_files', 'status', ('queued', 'parsing', 'ready', 'failed')),
        ('report_assets', 'status', ('queued', 'running', 'completed', 'failed')),
        ('model_calls', 'status', ('success', 'failed')),
    ]:
        assert all(v in c[table][col] for v in values), f'{table}.{col}'


@pytest.mark.skipif(os.environ.get('PIPESIGHT_COMPACT_COMMENT_REHEARSE') != '1', reason='Explicit canonical local rehearsal only')
def test_comment_only_pg18_updates_preserve_every_business_row() -> None:
    database = os.environ.get('PIPESIGHT_V3_COMMENT_DATABASE')
    if not database:
        pytest.skip('Runtime v5 comments require an explicit independent numeric-ID rehearsal database')
    assert re.fullmatch(r'pipesight_numeric_[a-z0-9_]+', database)
    root = Path(__file__).resolve().parents[2] / '.runtime/schema-rollout-ythNjXpI'
    connection = json.loads((root / 'rehearsal-connection.json').read_bytes())
    assert connection['host'] == '127.0.0.1' and connection['port'] == 19432
    assert connection['dbname'] == 'pipesight_rehearsal'
    container = 'pipesight-schema-rehearsal-ythnjxpi'
    labels = subprocess.run(['docker', 'inspect', '--format', '{{json .Config.Labels}}', container],
                            check=True, capture_output=True)
    assert json.loads(labels.stdout)['pipesight.schema-rollout'] == 'ythNjXpI'
    ports = subprocess.run(['docker', 'inspect', '--format', '{{json .NetworkSettings.Ports}}', container],
                           check=True, capture_output=True)
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in json.loads(ports.stdout)['5432/tcp']
    url = sa.URL.create('postgresql+psycopg2', username=connection['user'], password=connection['password'],
                        host=connection['host'], port=connection['port'], database=database)
    engine = sa.create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as bind:
            # Briefly prevent concurrent API writes from invalidating the row
            # comparison; readers remain allowed. This test changes comments only.
            bind.exec_driver_sql("SET LOCAL lock_timeout='5s'")
            bind.exec_driver_sql('LOCK TABLE ' + ','.join('public."' + n + '"' for n in sorted(PUBLIC_TABLES)) + ' IN SHARE MODE')
            def rows() -> dict:
                return {n: fingerprint([dict(r) for r in bind.execute(sa.text('SELECT * FROM public."' + n + '"')).mappings()])
                        for n in PUBLIC_TABLES}
            before = rows()
            assert apply_schema_comments(bind, allow_live=True) == {'tables': 29, 'columns': 343, 'views': 2}
            assert rows() == before
            assert apply_schema_comments(bind, allow_live=True) == {'tables': 29, 'columns': 343, 'views': 2}
            assert rows() == before
    finally:
        engine.dispose()
