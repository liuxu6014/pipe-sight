"""Offline regressions for complete model/catalog business-schema guards.

Only synthetic MetaData and catalog dictionaries are changed. No application
model, frozen artifact, PostgreSQL database or sequence is mutated by this file.
"""

import socket
from collections.abc import Iterator
from copy import deepcopy
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import business_schema as guard


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('Business schema guard edge tests must stay offline')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)


def metadata_specimen(*, fk_changes: dict | None = None, unique_changes: dict | None = None) -> sa.MetaData:
    """Independent tiny tables exercise the real helper without global models."""
    metadata = sa.MetaData()
    for name in guard.BUSINESS_TABLES:
        sa.Table(name, metadata, sa.Column('id', sa.BigInteger, primary_key=True), comment='离线业务表')
    for schema in ('public', 'other'):
        for name in ('sys_user', 'alternate_user'):
            sa.Table(name, metadata, sa.Column('id', sa.BigInteger, primary_key=True),
                     sa.Column('alternate_id', sa.BigInteger), schema=schema)
    table = metadata.tables['reports']
    for name in ('user_id', 'alternate_user_id'):
        table.append_column(sa.Column(name, sa.BigInteger))
    fk = {
        'schema': 'public', 'target': 'sys_user', 'target_column': 'id', 'column': 'user_id',
        'ondelete': 'RESTRICT', 'onupdate': 'NO ACTION', 'match': 'SIMPLE',
        'deferrable': False, 'initially': 'IMMEDIATE', 'omit': False,
    }
    fk.update(fk_changes or {})
    if not fk['omit']:
        table.append_constraint(sa.ForeignKeyConstraint(
            [fk['column']], [f'{fk["schema"]}.{fk["target"]}.{fk["target_column"]}'],
            name='fk_reports_owner', ondelete=fk['ondelete'], onupdate=fk['onupdate'],
            match=fk['match'], deferrable=fk['deferrable'], initially=fk['initially'],
        ))
    unique = {
        'name': 'uk_reports_owner', 'columns': ['user_id'], 'deferrable': False,
        'initially': 'IMMEDIATE', 'postgresql_nulls_not_distinct': False, 'omit': False,
    }
    unique.update(unique_changes or {})
    if not unique.pop('omit'):
        columns = unique.pop('columns')
        table.append_constraint(sa.UniqueConstraint(*columns, **unique))
    table.append_constraint(sa.CheckConstraint('id > 0', name='ck_reports_positive_id'))
    return metadata


@pytest.mark.parametrize('changes', [
    {'ondelete': 'CASCADE'}, {'onupdate': 'CASCADE'}, {'match': 'FULL'},
    {'deferrable': True}, {'initially': 'DEFERRED'}, {'schema': 'other'},
    {'target': 'alternate_user'}, {'target_column': 'alternate_id'},
    {'column': 'alternate_user_id'}, {'omit': True},
])
def test_model_fk_semantic_changes_always_change_frozen_declaration(changes: dict) -> None:
    baseline = guard.model_ddl(metadata_specimen())
    changed = guard.model_ddl(metadata_specimen(fk_changes=changes))
    assert changed != baseline, f'Foreign-key drift was omitted from model_ddl: {changes}'
    assert changed['reports']['foreign_keys'] != baseline['reports']['foreign_keys']


@pytest.mark.parametrize('changes', [
    {'name': 'uk_reports_owner_new'}, {'columns': ['alternate_user_id']},
    {'columns': ['user_id', 'alternate_user_id']}, {'deferrable': True},
    {'initially': 'DEFERRED'}, {'postgresql_nulls_not_distinct': True}, {'omit': True},
])
def test_model_unique_changes_always_change_frozen_declaration(changes: dict) -> None:
    baseline = guard.model_ddl(metadata_specimen())
    changed = guard.model_ddl(metadata_specimen(unique_changes=changes))
    assert changed != baseline, f'Unique-constraint drift was omitted from model_ddl: {changes}'
    assert changed['reports']['unique'] != baseline['reports']['unique']


def test_model_helper_is_repeatable_and_leaves_all_create_table_ddl_unchanged() -> None:
    metadata = metadata_specimen()
    dialect = postgresql.dialect()
    before = {name: str(CreateTable(table).compile(dialect=dialect)) for name, table in metadata.tables.items()}
    declaration = guard.model_ddl(metadata)
    assert declaration == guard.model_ddl(metadata)
    assert declaration['reports']['foreign_keys'] and declaration['reports']['unique']
    assert {name: str(CreateTable(table).compile(dialect=dialect))
            for name, table in metadata.tables.items()} == before


def catalog_specimen() -> dict:
    return {'reports': {
        'columns': [{
            'name': 'id', 'type': 'bigint', 'nullable': False,
            'default': "nextval('business_id_seq'::regclass)", 'identity': '',
            'identity_options': None, 'comment': '成果数值ID',
        }],
        'checks': [], 'indexes': [], 'unique': [], 'primary_key': ['id'], 'comment': '成果',
        'foreign_keys': [{
            'columns': ['user_id'], 'target_schema': 'public', 'target': 'sys_user',
            'target_columns': ['id'], 'validated': True, 'ondelete': 'RESTRICT',
            'onupdate': 'NO ACTION', 'match': 'SIMPLE', 'deferrable': False, 'initially': 'IMMEDIATE',
        }],
        'sequence': {
            'type': 'bigint', 'start_value': 1, 'min_value': 1,
            'max_value': '9223372036854775807', 'increment_by': 1,
            'cycle': False, 'cache_size': 1, 'owned_by': [],
        },
    }}


def assert_startup_rejects(monkeypatch: pytest.MonkeyPatch, actual: dict, expected: dict, kind: str) -> None:
    expected_before, actual_before = deepcopy(expected), deepcopy(actual)
    assert guard.schema_differences(actual, expected) == ['reports:' + kind]
    monkeypatch.setattr(guard, 'load_frozen', lambda: {'catalog': expected, 'model_ddl': {}})
    monkeypatch.setattr(guard, 'catalog', lambda _connection: actual)
    connection = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    with pytest.raises(RuntimeError, match='reports:' + kind):
        guard.validate_business_schema(connection)
    assert expected == expected_before and actual == actual_before


@pytest.mark.parametrize('key,value', [('target_schema', 'other'), ('validated', False)])
def test_actual_fk_schema_or_validation_drift_blocks_startup(monkeypatch: pytest.MonkeyPatch, key: str, value: object) -> None:
    expected = catalog_specimen()
    actual = deepcopy(expected)
    actual['reports']['foreign_keys'][0][key] = value
    assert_startup_rejects(monkeypatch, actual, expected, 'foreign_keys')


@pytest.mark.parametrize('key,value', [
    ('type', 'integer'), ('start_value', 2), ('min_value', 0), ('max_value', 100),
    ('increment_by', -1), ('cycle', True), ('cache_size', 10), ('owned_by', ['public.reports.id']),
])
def test_actual_shared_sequence_definition_drift_blocks_startup(monkeypatch: pytest.MonkeyPatch, key: str, value: object) -> None:
    expected = catalog_specimen()
    actual = deepcopy(expected)
    actual['reports']['sequence'][key] = value
    assert_startup_rejects(monkeypatch, actual, expected, 'sequence')


def test_missing_shared_sequence_descriptor_blocks_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = catalog_specimen()
    actual = deepcopy(expected)
    del actual['reports']['sequence']
    assert_startup_rejects(monkeypatch, actual, expected, 'sequence')


@pytest.mark.parametrize('key,value', [
    ('always', True), ('start', 2), ('increment', -1), ('minvalue', 0),
    ('maxvalue', 100), ('cycle', True), ('cache', 10),
])
def test_actual_identity_options_drift_blocks_startup(monkeypatch: pytest.MonkeyPatch, key: str, value: object) -> None:
    expected = catalog_specimen()
    column = expected['reports']['columns'][0]
    column.update(default=None, identity='d', identity_options={
        'always': False, 'start': 1, 'increment': 1, 'minvalue': 1,
        'maxvalue': 9223372036854775807, 'cycle': False, 'cache': 1,
    })
    actual = deepcopy(expected)
    actual['reports']['columns'][0]['identity_options'][key] = value
    assert_startup_rejects(monkeypatch, actual, expected, 'columns')


def test_unchanged_catalog_is_accepted_without_repair_or_counter_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = catalog_specimen()
    actual = deepcopy(expected)
    monkeypatch.setattr(guard, 'load_frozen', lambda: {'catalog': expected})
    monkeypatch.setattr(guard, 'catalog', lambda _connection: actual)
    # No execute/DDL API: this path must stay read-only and must not allocate IDs.
    connection = SimpleNamespace(dialect=SimpleNamespace(name='postgresql'))
    guard.validate_business_schema(connection)
    assert expected == actual


@pytest.mark.parametrize('wrong_type', [
    'timestamp with time zone', 'timestamp(0) with time zone',
    'timestamp without time zone', 'timestamp(6) without time zone',
])
def test_v5_audit_timezone_or_precision_drift_blocks_startup(monkeypatch: pytest.MonkeyPatch, wrong_type: str) -> None:
    expected = catalog_specimen()
    expected['reports']['columns'] = [{
        'name': 'created_at', 'type': 'timestamp(0) without time zone',
        'nullable': False, 'default': "date_trunc('second', timezone('Asia/Shanghai', now()))",
        'identity': '', 'comment': '北京时间创建时间，精度到秒',
    }]
    actual = deepcopy(expected)
    actual['reports']['columns'][0]['type'] = wrong_type
    assert_startup_rejects(monkeypatch, actual, expected, 'columns')


class CatalogRows:
    def __init__(self, values: list) -> None:
        self.values = deepcopy(values)

    def mappings(self) -> 'CatalogRows':
        return self

    def scalars(self) -> 'CatalogRows':
        return self

    def first(self) -> object:
        return self.values[0] if self.values else None

    def all(self) -> list:
        return self.values

    def __iter__(self) -> Iterator:
        return iter(self.values)


class CatalogConnection:
    """Only known SELECTs exist; writes and real connections are impossible."""

    def __init__(self) -> None:
        self.target_schema = 'public'
        self.validated = True
        self.sequence = deepcopy(catalog_specimen()['reports']['sequence'])
        self.owned_by = self.sequence.pop('owned_by')
        self.identity_options = {
            'always': False, 'start': 1, 'increment': 1, 'minvalue': 1,
            'maxvalue': '9223372036854775807', 'cycle': False, 'cache': 1,
        }

    def execute(self, sql: object) -> CatalogRows:
        query = str(sql)
        assert query.lstrip().startswith('SELECT'), 'Catalog extraction must never mutate the database'
        if 'FROM pg_attribute' in query:
            return CatalogRows([{
                'table_name': 'reports', 'name': 'id', 'type': 'bigint',
                'nullable': False, 'default': None, 'identity': 'd', 'comment': '成果ID',
            }])
        if "c.contype='f'" in query:
            return CatalogRows([{
                'table_name': 'reports', 'name': 'fk_reports_owner',
                'target_schema': self.target_schema, 'validated': self.validated,
            }])
        if 'FROM pg_sequences' in query:
            return CatalogRows([self.sequence] if self.sequence is not None else [])
        if 'FROM pg_depend' in query:
            return CatalogRows(self.owned_by)
        if "c.contype='c'" in query or 'FROM pg_index' in query:
            return CatalogRows([])
        raise AssertionError('Unexpected catalog query: ' + query)


def capture_catalog(monkeypatch: pytest.MonkeyPatch, connection: CatalogConnection) -> dict:
    # Inspector is deliberately incomplete for FK schema/validation: those
    # attributes must come from pg_constraint, not inferred from search_path.
    inspector = SimpleNamespace(
        get_table_comment=lambda *_args, **_kwargs: {'text': '成果'},
        get_columns=lambda *_args, **_kwargs: [{'name': 'id', 'identity': deepcopy(connection.identity_options)}],
        get_pk_constraint=lambda *_args, **_kwargs: {'constrained_columns': ['id']},
        get_unique_constraints=lambda *_args, **_kwargs: [],
        get_foreign_keys=lambda *_args, **_kwargs: [{
            'name': 'fk_reports_owner', 'constrained_columns': ['user_id'],
            'referred_schema': None, 'referred_table': 'sys_user',
            'referred_columns': ['id'], 'options': {'ondelete': 'RESTRICT'},
        }],
    )
    monkeypatch.setattr(guard.sa, 'inspect', lambda _connection: inspector)
    return guard.catalog(connection, tables=('reports',))


@pytest.mark.parametrize('attribute,value', [('target_schema', 'other'), ('validated', False)])
def test_catalog_capture_retains_actual_fk_schema_and_validation(monkeypatch: pytest.MonkeyPatch, attribute: str, value: object) -> None:
    connection = CatalogConnection()
    expected = capture_catalog(monkeypatch, connection)
    setattr(connection, attribute, value)
    actual = capture_catalog(monkeypatch, connection)
    assert actual['reports']['foreign_keys'][0][attribute] == value
    assert guard.schema_differences(actual, expected) == ['reports:foreign_keys']


@pytest.mark.parametrize('key,value', [
    ('type', 'integer'), ('start_value', 2), ('min_value', 0), ('max_value', 100),
    ('increment_by', -1), ('cycle', True), ('cache_size', 10),
])
def test_catalog_capture_retains_sequence_definition(monkeypatch: pytest.MonkeyPatch, key: str, value: object) -> None:
    connection = CatalogConnection()
    expected = capture_catalog(monkeypatch, connection)
    connection.sequence[key] = value
    actual = capture_catalog(monkeypatch, connection)
    assert actual['reports']['sequence'][key] == value
    assert guard.schema_differences(actual, expected) == ['reports:sequence']
    assert not {'last_value', 'is_called'} & actual['reports']['sequence'].keys()


def test_catalog_capture_retains_sequence_ownership_and_absence(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = CatalogConnection()
    expected = capture_catalog(monkeypatch, connection)
    connection.owned_by = ['public.reports.id']
    actual = capture_catalog(monkeypatch, connection)
    assert actual['reports']['sequence']['owned_by'] == connection.owned_by
    assert guard.schema_differences(actual, expected) == ['reports:sequence']
    connection.sequence = None
    actual = capture_catalog(monkeypatch, connection)
    assert actual['reports']['sequence'] is None
    assert guard.schema_differences(actual, expected) == ['reports:sequence']


@pytest.mark.parametrize('key,value', [
    ('always', True), ('start', 2), ('increment', -1), ('minvalue', 0),
    ('maxvalue', 100), ('cycle', True), ('cache', 10),
])
def test_catalog_capture_retains_identity_options(monkeypatch: pytest.MonkeyPatch, key: str, value: object) -> None:
    connection = CatalogConnection()
    expected = capture_catalog(monkeypatch, connection)
    connection.identity_options[key] = value
    actual = capture_catalog(monkeypatch, connection)
    assert actual['reports']['columns'][0]['identity_options'][key] == value
    assert guard.schema_differences(actual, expected) == ['reports:columns']
