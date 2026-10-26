"""Offline PG migration orchestration tests, NOT PostgreSQL rollback evidence.

The connection double records DDL and models savepoint state only. No engine,
socket, service, or user database is opened; real asyncpg rehearsals are separate.
"""

from __future__ import annotations

import json
import re
import socket
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa

from app import numeric_id_migration as migration

if TYPE_CHECKING:
    from pathlib import Path

PRIVATE_FILE_MODE = 0o600


class OfflineSavepoint:
    def __init__(self, bind: OfflinePG) -> None:
        self.bind = bind

    def __enter__(self) -> OfflineSavepoint:
        self.before = deepcopy(self.bind.state)
        self.bind.events.append('savepoint')
        return self

    def __exit__(self, error_type: Any, error: Any, traceback: Any) -> bool:
        if error_type:
            self.bind.state = self.before
            self.bind.events.append('rollback_savepoint')
        else:
            self.bind.events.append('release_savepoint')
        return False


class OfflinePG:
    def __init__(self) -> None:
        self.engine = SimpleNamespace(url=sa.engine.make_url('postgresql+asyncpg://offline@127.0.0.1:19432/test'))
        self.outer_transaction = True
        self.events = []
        self.statements = []
        self.state = {'columns': set(), 'sequence': False, 'dropped_fk': False}
        self.fail_sql = None

    def in_transaction(self) -> bool:
        return self.outer_transaction

    def begin_nested(self) -> OfflineSavepoint:
        return OfflineSavepoint(self)

    def commit(self) -> None:
        pytest.fail('Migration must not commit the caller transaction')

    def rollback(self) -> None:
        pytest.fail('Migration must not roll back the caller transaction')

    def scalar(self, statement: Any) -> str | None:
        assert 'to_regclass' in str(statement)
        return 'business_id_seq' if self.state['sequence'] else None

    def execute(self, statement: Any, parameters: Any = None) -> SimpleNamespace:
        sql = str(statement)
        self.statements.append((sql, deepcopy(parameters)))
        if 'SELECT count(*)' in sql:
            return SimpleNamespace(one=lambda: (0, 'offline-backup-fingerprint'))
        return SimpleNamespace()

    def exec_driver_sql(self, sql: str) -> None:
        self.statements.append((sql, None))
        if self.fail_sql and self.fail_sql in sql:
            raise RuntimeError('injected DDL failure')
        if ' TYPE bigint ' in sql:
            match = re.search(r'public\."(\w+)" ALTER COLUMN "(\w+)"', sql)
            assert match
            self.state['columns'].add(match.groups())
        if sql.startswith('CREATE SEQUENCE'):
            self.state['sequence'] = True
        if ' DROP CONSTRAINT ' in sql:
            self.state['dropped_fk'] = True
        if ' ADD CONSTRAINT ' in sql:
            self.state['dropped_fk'] = False


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs) -> None:
        pytest.fail('Offline migration tests must never open a network connection')

    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


@pytest.fixture
def offline_migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    bind = OfflinePG()
    root = tmp_path / 'private-backup'
    root.mkdir(mode=0o700)
    dump = b'Synthetic offline dump: not a real database backup'
    (root / 'database-before.dump').write_bytes(dump)
    tables = set(migration.TABLE_COMMENTS)
    source = {table: [] for table in tables}
    source['categories'] = [{'id': 'old-category', 'parent_id': None}]
    foreign_keys = [{
        'table': 'categories', 'columns': ['parent_id'], 'target': 'categories',
        'target_columns': ['id'], 'name': 'fk_offline_parent',
    }]
    definitions = [{
        'table_name': 'categories', 'name': 'fk_offline_parent', 'type': 'f',
        'definition': 'FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE RESTRICT',
        'validated': True,
    }]
    manifest = {
        'revision': '20261025_restore_ruoyi_names', 'sha256': sha256(dump).hexdigest(),
        'tables': sorted(tables),
        'fingerprints': {table: [0, 'offline-backup-fingerprint'] for table in tables},
    }
    context = SimpleNamespace(bind=bind, root=root, manifest=manifest, source=source, phases=[], corrupt=False,
                              index_drift=False, default_drift=False)

    class Inspector:
        def get_columns(self, table: str, *, schema: str) -> list[dict]:
            assert schema == 'public'
            names = ['id', 'parent_id'] if table == 'categories' else ['id']
            return [{
                'name': column,
                'type': sa.BigInteger() if (table, column) in bind.state['columns'] else (
                    sa.String() if table in migration.BUSINESS_ID_TABLES else sa.Integer()
                ),
                'nullable': column != 'id',
                'default': (
                    "nextval('business_id_seq'::regclass)"
                    if bind.state['sequence'] and table in migration.BUSINESS_ID_TABLES and column == 'id'
                    else '0' if context.default_drift and bind.state['sequence'] and column == 'parent_id' else None
                ),
            } for column in names]

        def get_foreign_keys(self, table: str, *, schema: str) -> list[dict]:
            return [{
                'name': 'fk_offline_parent', 'constrained_columns': ['parent_id'],
                'referred_table': 'categories', 'referred_columns': ['id'], 'referred_schema': 'public',
            }] if table == 'categories' else []

    def rows(connection: OfflinePG, selected_tables: set[str], *, phase: str = 'source') -> dict:
        assert connection is bind and selected_tables == tables
        context.phases.append(phase)
        if phase == 'source':
            return deepcopy(source)
        assert phase == 'target'
        result = migration.build_plan(source, foreign_keys).target_rows
        if context.corrupt:
            result['categories'].append({'id': 999, 'parent_id': None})
        return result

    monkeypatch.setattr(migration.sa, 'inspect', lambda connection: Inspector())
    monkeypatch.setattr(migration, '_inventory', lambda connection: tables)
    monkeypatch.setattr(migration, '_constraints', lambda connection: deepcopy(definitions))
    monkeypatch.setattr(migration, '_owners', lambda connection: [(123, 'categories', 456, None)])
    monkeypatch.setattr(migration, '_indexes', lambda connection: [
        ('categories', 'offline_index', 'changed' if context.index_drift and bind.state['sequence'] else 'original',
         True, True),
    ])
    monkeypatch.setattr(migration, '_rows', rows)
    context.run = lambda: migration.migrate_numeric_ids(bind, manifest=manifest, backup_dir=root)
    return context


def test_success_releases_savepoint_without_committing_outer_transaction(offline_migration: SimpleNamespace) -> None:
    case = offline_migration
    result = case.run()
    assert result['numeric_primary_keys'] == len(migration.BUSINESS_ID_TABLES)
    assert result['converted_columns'] == len(migration.BUSINESS_ID_TABLES) + 1
    assert result['mapped_records'] == 1
    assert result['all_projected_rows_verified'] is True
    assert case.bind.events == ['savepoint', 'release_savepoint']
    assert case.bind.in_transaction()
    assert case.phases == ['source', 'target']
    sql = [statement for statement, _ in case.bind.statements]
    drop = next(i for i, value in enumerate(sql) if ' DROP CONSTRAINT ' in value)
    alter = next(i for i, value in enumerate(sql) if ' TYPE bigint ' in value)
    restore = next(i for i, value in enumerate(sql) if ' ADD CONSTRAINT ' in value)
    assert drop < alter < restore
    assert not case.bind.state['dropped_fk']
    archive = case.root / 'numeric-id-mapping.json'
    assert archive.stat().st_mode & 0o777 == PRIVATE_FILE_MODE
    payload = json.loads(archive.read_text())
    assert payload['mappings']['categories'] == {'old-category': 1}
    assert payload['source_fingerprints']['categories'] == migration.fingerprint(case.source['categories'])


@pytest.mark.parametrize('failure', [' TYPE bigint ', 'CREATE SEQUENCE', 'COMMENT ON COLUMN'])
def test_ddl_failure_propagates_and_rolls_back_savepoint_only(offline_migration: SimpleNamespace, failure: str) -> None:
    case = offline_migration
    before = deepcopy(case.bind.state)
    case.bind.fail_sql = failure
    with pytest.raises(RuntimeError, match='injected DDL failure'):
        case.run()
    assert case.bind.state == before
    assert case.bind.events == ['savepoint', 'rollback_savepoint']
    assert case.bind.in_transaction()
    # Audit survives DB rollback, and exclusive creation prevents accidental reuse.
    assert (case.root / 'numeric-id-mapping.json').exists()
    with pytest.raises(FileExistsError):
        case.run()
    assert case.bind.state == before


def test_target_projection_mismatch_rolls_back_after_ddl(offline_migration: SimpleNamespace) -> None:
    case = offline_migration
    before = deepcopy(case.bind.state)
    case.corrupt = True
    with pytest.raises(RuntimeError, match='Target rows differ'):
        case.run()
    assert case.phases == ['source', 'target']
    assert case.bind.state == before
    assert case.bind.events[-1] == 'rollback_savepoint'


@pytest.mark.parametrize('drift,message', [('index_drift', 'semantics changed'),
                                          ('default_drift', 'Unrelated column default changed')])
def test_index_or_nonprimary_default_drift_is_rejected_and_rolled_back(
    offline_migration: SimpleNamespace, drift: str, message: str,
) -> None:
    case = offline_migration
    before = deepcopy(case.bind.state)
    setattr(case, drift, True)
    with pytest.raises(RuntimeError, match=message):
        case.run()
    assert case.bind.events == ['savepoint', 'rollback_savepoint']
    assert case.bind.state == before
    assert case.bind.in_transaction()


@pytest.mark.parametrize('gate,message', [
    ('transaction', 'caller-owned'), ('host', 'explicit'), ('permissions', 'private'),
    ('revision', 'revision'), ('sha', 'SHA-256'), ('tables', 'table contract'),
])
def test_preflight_gate_rejects_before_any_savepoint_or_sql(
    offline_migration: SimpleNamespace, gate: str, message: str,
) -> None:
    case = offline_migration
    if gate == 'transaction':
        case.bind.outer_transaction = False
    elif gate == 'host':
        case.bind.engine.url = sa.engine.make_url('postgresql://offline@production:5432/pipesight')
    elif gate == 'permissions':
        case.root.chmod(0o755)
    elif gate == 'revision':
        case.manifest['revision'] = 'incorrect'
    elif gate == 'sha':
        case.manifest['sha256'] = '0' * 64
    else:
        case.manifest['tables'] = []
    with pytest.raises(RuntimeError, match=message):
        case.run()
    assert case.bind.events == []
    assert case.bind.statements == []
    assert not (case.root / 'numeric-id-mapping.json').exists()


def test_changed_source_fingerprint_refuses_ddl_and_mapping_archive(offline_migration: SimpleNamespace) -> None:
    case = offline_migration
    case.manifest['fingerprints']['categories'] = [100, 'changed']
    with pytest.raises(RuntimeError, match='Source changed since backup'):
        case.run()
    assert case.bind.events == ['savepoint', 'rollback_savepoint']
    assert not any('ALTER TABLE' in sql for sql, _ in case.bind.statements)
    assert not (case.root / 'numeric-id-mapping.json').exists()


def test_archive_is_required_before_first_mutating_ddl(
    offline_migration: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = offline_migration

    def archive_failure(*args) -> None:
        raise OSError('offline archive unavailable')

    monkeypatch.setattr(migration, '_archive', archive_failure)
    with pytest.raises(OSError, match='archive unavailable'):
        case.run()
    assert not any(sql.startswith(('CREATE ', 'ALTER ', 'UPDATE ')) for sql, _ in case.bind.statements)
    assert case.bind.events[-1] == 'rollback_savepoint'


@pytest.mark.parametrize('empty', [False, True])
def test_shared_sequence_setval_called_flag_distinguishes_empty_dataset(
    offline_migration: SimpleNamespace, empty: bool,
) -> None:
    case = offline_migration
    if empty:
        case.source['categories'] = []
    case.run()
    parameters = [params for sql, params in case.bind.statements if 'SELECT setval(' in sql]
    assert parameters == [{'value': 1, 'called': not empty}]


def test_rows_uses_distinct_source_target_prepared_statement_cache_keys() -> None:
    statements = []

    def execute(statement: Any) -> SimpleNamespace:
        statements.append(str(statement))
        return SimpleNamespace(mappings=lambda: [{'id': 'offline'}])

    bind = SimpleNamespace(execute=execute)
    assert migration._rows(bind, {'categories'}) == {'categories': [{'id': 'offline'}]}
    migration._rows(bind, {'categories'}, phase='target')
    assert statements[0] != statements[1]
    assert 'numeric_source' in statements[0] and 'numeric_target' in statements[1]
    with pytest.raises(ValueError, match='phase'):
        migration._rows(bind, {'categories'}, phase='unexpected')
    assert len(statements) == len({'source', 'target'})
