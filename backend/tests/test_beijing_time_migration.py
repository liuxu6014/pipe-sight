"""Offline migration guards and SQL shape, NOT real PostgreSQL conversion evidence.

No engine/socket is opened. Savepoint doubles verify failure orchestration only;
the migration owner performs actual PostgreSQL/asyncpg/data rehearsals separately.
"""

from __future__ import annotations

import ast
import json
import socket
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.engine import make_url

from app import beijing_time_migration as migration
from app.business_schema import BUSINESS_TABLES, load_frozen


class Savepoint:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.original = deepcopy(self.connection.changed)
        self.connection.events.append('savepoint')

    def __exit__(self, error_type, error, traceback):
        if error_type:
            self.connection.changed = self.original
            self.connection.events.append('rollback_savepoint')
        else:
            self.connection.events.append('release_savepoint')
        return False


class OfflineConnection:
    def __init__(self):
        self.engine = NS(url=make_url('postgresql+asyncpg://offline@127.0.0.1:19432/pipesight_beijing_initial'))
        self.dialect = NS(name='postgresql')
        self.outer = True
        self.statements, self.events, self.changed = [], [], []
        self.fail_sql = None

    def in_transaction(self):
        return self.outer

    def begin_nested(self):
        return Savepoint(self)

    def commit(self):
        pytest.fail('The migration must never commit its caller-owned transaction')

    def rollback(self):
        pytest.fail('The migration must never roll back its caller-owned transaction')

    def exec_driver_sql(self, statement):
        self.statements.append(statement)
        if self.fail_sql and self.fail_sql in statement:
            raise RuntimeError('injected DDL failure')
        if statement.startswith(('ALTER ', 'COMMENT ')):
            self.changed.append(statement)
        return NS(scalar_one=lambda: migration.PREVIOUS_REVISION)


@pytest.fixture(autouse=True)
def forbid_connections(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('This test suite never opens a socket or database')

    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


def synthetic_target(previous):
    """Exact intended delta; independent of the concurrently generated v5 file."""
    target = deepcopy(previous)
    for name in BUSINESS_TABLES:
        for column in target['catalog'][name]['columns']:
            if column['name'] in migration.AUDIT_COLUMNS:
                column['type'] = 'timestamp(0) without time zone'
                column['comment'] = '北京时间；秒精度'
        for column in target['model_ddl'][name]['columns']:
            if column['name'] in migration.AUDIT_COLUMNS:
                column['type'] = 'TIMESTAMP(0) WITHOUT TIME ZONE'
                column['comment'] = '北京时间；秒精度'
                column['default'] = "date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')"
    for check in target['catalog']['collection_runs']['checks']:
        if check['name'] == 'ck_collection_runs_times':
            check['definition'] = check['definition'].replace('created_at', "(created_at AT TIME ZONE 'Asia/Shanghai')")
    for check in target['model_ddl']['collection_runs']['checks']:
        if check['name'] == 'ck_collection_runs_times':
            check['ddl'] = check['ddl'].replace('created_at', "(created_at AT TIME ZONE 'Asia/Shanghai')")
    return target


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    previous = load_frozen('v4')
    target = synthetic_target(previous)
    connection = OfflineConnection()
    tables = sorted(set(BUSINESS_TABLES) | set(migration.PROTECTED_TABLES))
    assert len(tables) == 29
    rows = {name: [3, 'before-' + name] for name in tables}
    projected = {name: [3, 'projected-' + name] for name in BUSINESS_TABLES}
    root = tmp_path / 'backup'
    root.mkdir(mode=0o700)
    raw = b'offline-placeholder-not-a-real-dump'
    (root / 'database-before.dump').write_bytes(raw)
    manifest = {
        'revision': migration.PREVIOUS_REVISION,
        'tables': tables,
        'fingerprints': rows,
        'sha256': sha256(raw).hexdigest(),
    }
    (root / 'database-before.json').write_text(json.dumps(manifest))
    state = NS(
        source=deepcopy(previous['catalog']),
        target=deepcopy(target['catalog']),
        before_rows=deepcopy(rows),
        after_rows=deepcopy(rows),
        expected=deepcopy(projected),
        actual=deepcopy(projected),
        protected={'sys_user': 'unchanged'},
        owners=['unchanged'],
        objects={'views': [], 'sequences': []},
    )
    state.after_protected, state.after_owners, state.after_objects = (
        deepcopy(state.protected),
        deepcopy(state.owners),
        deepcopy(state.objects),
    )
    loaded, archived = [], []

    def frozen(version):
        loaded.append(version)
        return {'v4': previous, 'v5': target}[version]

    def catalog(bind, selected=BUSINESS_TABLES):
        after = bool(bind.changed)
        if selected == migration.PROTECTED_TABLES:
            return state.after_protected if after else state.protected
        return state.target if after else state.source

    monkeypatch.setattr(migration, 'load_frozen', frozen)
    monkeypatch.setattr(migration.sa, 'inspect', lambda bind: NS(get_table_names=lambda **kwargs: tables))
    monkeypatch.setattr(migration, 'catalog', catalog)
    monkeypatch.setattr(
        migration, 'row_fingerprints', lambda bind, names: state.after_rows if bind.changed else state.before_rows
    )
    monkeypatch.setattr(
        migration, 'projected_fingerprints', lambda bind, columns, before: state.expected if before else state.actual
    )
    monkeypatch.setattr(migration, 'table_owners', lambda bind: state.after_owners if bind.changed else state.owners)
    monkeypatch.setattr(
        migration, 'framework_objects', lambda bind: state.after_objects if bind.changed else state.objects
    )
    monkeypatch.setattr(migration, 'archive', lambda path, data: archived.append((path.name, deepcopy(data))))
    return NS(
        connection=connection,
        root=root,
        state=state,
        previous=previous,
        target=target,
        loaded=loaded,
        archived=archived,
        run=lambda: migration.migrate_beijing_audit_time(connection, backup_dir=root),
    )


def test_scope_is_only_27_audit_columns_on_15_business_tables(scenario):
    selected = migration.validate_conversion_scope(scenario.previous, scenario.target)
    assert set(selected) == set(BUSINESS_TABLES)
    assert sum(map(len, selected.values())) == 27
    assert not set(selected) & set(migration.PROTECTED_TABLES)
    assert not any(name.startswith('sys_') for name in selected)
    assert selected['model_calls'] == selected['basket_items'] == selected['report_versions'] == ['created_at']


def test_success_pins_both_contract_versions_and_never_commits_or_touches_protected_ddl(scenario):
    result = scenario.run()
    assert scenario.loaded == ['v4', 'v5']
    assert result['business_data'] == 'exact_expected_projection' and result['audit_columns'] == 27
    sql = scenario.connection.statements
    alterations = [s for s in sql if ' TYPE timestamp(0) without time zone USING ' in s]
    assert len(alterations) == 27
    for statement in alterations:
        assert "date_trunc('second'," in statement and "AT TIME ZONE 'Asia/Shanghai')" in statement
        assert 'created_at' in statement or 'updated_at' in statement
        assert not any(name in statement for name in ('published_at', 'available_at', 'lease_expires_at'))
    for statement in sql:
        if statement.startswith(('ALTER ', 'COMMENT ')):
            assert not any(
                'public.' + migration.quote_identifier(name) in statement for name in migration.PROTECTED_TABLES
            )
    assert not any(s.startswith(('UPDATE ', 'DELETE ', 'TRUNCATE ', 'INSERT ')) for s in sql)
    assert sql.index('ALTER TABLE public.collection_runs DROP CONSTRAINT ck_collection_runs_times') < sql.index(
        alterations[0]
    )
    assert scenario.connection.events == ['savepoint', 'release_savepoint']


@pytest.mark.parametrize('drift', ['nullable', 'name', 'non_audit_type', 'foreign_keys', 'checks', 'inventory'])
def test_unrelated_frozen_scope_drift_is_rejected(scenario, drift):
    target = deepcopy(scenario.target)
    table = target['catalog']['reports']
    if drift == 'nullable':
        next(c for c in table['columns'] if c['name'] == 'created_at')['nullable'] = True
    elif drift == 'name':
        next(c for c in table['columns'] if c['name'] == 'created_at')['name'] = 'other_clock'
    elif drift == 'non_audit_type':
        next(c for c in table['columns'] if c['name'] == 'content')['type'] = 'jsonb'
    elif drift == 'foreign_keys':
        table['foreign_keys'] = []
    elif drift == 'checks':
        table['checks'][0]['definition'] = 'CHECK (true)'
    else:
        target['catalog'].pop('papers')
    with pytest.raises(RuntimeError):
        migration.validate_conversion_scope(scenario.previous, target)


@pytest.mark.parametrize(
    'defect',
    ['missing_rows', 'changed_null', 'protected_rows', 'protected_schema', 'owners', 'objects', 'target_schema'],
)
def test_post_conversion_invariant_failure_rolls_back_savepoint(scenario, defect):
    state = scenario.state
    if defect == 'missing_rows':
        state.actual['reports'][0] -= 1
    elif defect == 'changed_null':
        state.actual['papers'][1] = 'SQL-null-became-another-value'
    elif defect == 'protected_rows':
        state.after_rows['sys_user'][1] = 'changed'
    elif defect == 'protected_schema':
        state.after_protected['sys_user'] = 'changed'
    elif defect == 'owners':
        state.after_owners.append('changed')
    elif defect == 'objects':
        state.after_objects['sequences'].append('changed')
    else:
        state.target['reports']['comment'] = 'changed'
    with pytest.raises(RuntimeError):
        scenario.run()
    assert scenario.connection.changed == []
    assert scenario.connection.events[-1] == 'rollback_savepoint'


@pytest.mark.parametrize('defect', ['backup_checksum', 'backup_rows', 'source_schema'])
def test_source_or_backup_drift_rejected_before_first_ddl(scenario, defect):
    if defect == 'backup_checksum':
        (scenario.root / 'database-before.dump').write_bytes(b'tampered')
    elif defect == 'backup_rows':
        scenario.state.before_rows['papers'][0] = 0
    else:
        scenario.state.source['papers']['columns'][0]['type'] = 'text'
    with pytest.raises(RuntimeError):
        scenario.run()
    assert not scenario.connection.changed
    assert not any(sql.startswith(('ALTER ', 'COMMENT ')) for sql in scenario.connection.statements)


def test_ddl_exception_rolls_back_the_savepoint_not_the_caller(scenario):
    scenario.connection.fail_sql = 'TYPE timestamp(0)'
    with pytest.raises(RuntimeError, match='injected'):
        scenario.run()
    assert scenario.connection.events[-1] == 'rollback_savepoint' and not scenario.connection.changed


@pytest.mark.parametrize(
    'url', ['postgresql://offline@remote.invalid:19432/test', 'postgresql://offline@127.0.0.1:5432/test']
)
def test_remote_or_wrong_port_is_rejected_before_sql(scenario, url):
    scenario.connection.engine.url = make_url(url)
    with pytest.raises(RuntimeError, match='allow_live'):
        scenario.run()
    assert scenario.connection.statements == []


def test_source_database_name_requires_explicit_live_authorization_even_on_local_rehearsal_port(scenario):
    scenario.connection.engine.url = make_url('postgresql://offline@127.0.0.1:19432/pipesight')
    with pytest.raises(RuntimeError, match='[Ll]ive|allow_live|source|源'):
        scenario.run()
    assert scenario.connection.statements == []


def test_projection_sql_retains_nulls_all_other_columns_and_unchanged_instants():
    captured = []

    def execute(sql):
        captured.append(sql)
        return NS(one=lambda: (2, 'opaque-server-row-hash'))

    connection = NS(exec_driver_sql=execute)
    before = migration.projected_fingerprints(connection, {'reports': ['created_at', 'updated_at']}, before=True)
    assert before == {'reports': [2, 'opaque-server-row-hash']}
    sql = captured[-1]
    assert 'to_jsonb(t) || jsonb_build_object(' in sql
    assert "'created_at',date_trunc('second',t.\"created_at\" AT TIME ZONE 'Asia/Shanghai')" in sql
    assert 'count(*)' in sql and 'ORDER BY h' in sql
    assert not any(field in sql for field in ('published_at', 'available_at', 'finished_at', 'checkpoint'))
    migration.projected_fingerprints(connection, {'reports': ['created_at', 'updated_at']}, before=False)
    assert 'jsonb_build_object' not in captured[-1] and 'to_jsonb(t)' in captured[-1]
    assert 'IS NOT NULL' not in sql  # NULL audit clocks cannot filter out rows.


@pytest.mark.parametrize(
    'instant,expected',
    [
        ('2026-10-25T16:59:59.999999+00:00', '2026-10-26 00:59:59'),
        ('2026-10-25T23:59:59.500001+08:00', '2026-10-25 23:59:59'),
        ('2024-02-29T15:59:59.000001+00:00', '2024-02-29 23:59:59'),
    ],
)
def test_independent_wall_clock_projection_examples_floor_not_round(instant, expected):
    # Independent expectation only: SQL shape above, actual PG evaluation is separate.
    value = datetime.fromisoformat(instant)
    projected = value.astimezone(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None, microsecond=0)
    assert projected.strftime('%Y-%m-%d %H:%M:%S') == expected
    assert projected.replace(tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc) <= value


def test_historical_consistency_migration_stays_pinned_to_v4_without_mutable_orm_import():
    def frozen_calls(path, function):
        # co_firstlineno can point at a different function if a peer saves source
        # after import. Parse the current file, not linecache/inspect offsets.
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
        calls = [
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'load_frozen'
        ]
        assert calls and all(len(call.args) == 1 and not call.keywords for call in calls)
        assert all(isinstance(call.args[0], ast.Constant) for call in calls)
        assert not any(isinstance(n, ast.Name) and n.id == 'register_sqlalchemy_models' for n in ast.walk(node))
        assert not any(
            isinstance(n, ast.Attribute)
            and n.attr == 'metadata'
            and isinstance(n.value, ast.Name)
            and n.value.id == 'Base'
            for n in ast.walk(node)
        )
        return [call.args[0].value for call in sorted(calls, key=lambda call: (call.lineno, call.col_offset))]

    path = Path(migration.__file__)
    assert frozen_calls(path.with_name('business_schema_migration.py'), 'migrate_business_consistency') == ['v4']
    assert frozen_calls(path, 'migrate_beijing_audit_time') == ['v4', 'v5']


def test_actual_frozen_v5_is_exact_narrow_conversion_with_explicit_beijing_defaults_and_check():
    previous, target = load_frozen('v4'), load_frozen('v5')
    selected = migration.validate_conversion_scope(previous, target)
    assert sum(map(len, selected.values())) == 27
    for table, fields in selected.items():
        for column in target['model_ddl'][table]['columns']:
            if column['name'] in fields:
                assert column['type'] == 'TIMESTAMP(0) WITHOUT TIME ZONE'
                assert column['default'] == "date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')"
    old_check = next(
        c['definition']
        for c in previous['catalog']['collection_runs']['checks']
        if c['name'] == 'ck_collection_runs_times'
    )
    new_check = next(
        c['definition']
        for c in target['catalog']['collection_runs']['checks']
        if c['name'] == 'ck_collection_runs_times'
    )
    # No weakening of predicates, NULL branches, or ordering while making the
    # mixed timestamp comparison session-timezone independent.
    normalized = new_check.replace("(created_at AT TIME ZONE 'Asia/Shanghai'::text)", 'created_at')
    assert normalized.replace("(created_at AT TIME ZONE 'Asia/Shanghai')", 'created_at') == old_check


def test_alembic_downgrade_cannot_invent_discarded_subseconds():
    revision = Path(migration.__file__).parents[2] / 'alembic/versions/20261025_beijing_audit_time.py'
    assert 'discarded sub-second precision cannot be reconstructed' in revision.read_text()
