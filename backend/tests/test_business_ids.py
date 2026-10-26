"""Offline numeric-ID contracts; PostgreSQL SQL is compiled, never executed.

SQLite INTEGER PRIMARY KEY allocates per table. PostgreSQL uses one shared
business_id_seq; SQLite checks are not evidence of PostgreSQL sequence state.
"""

import socket
from collections.abc import Generator
from decimal import Decimal

import pytest
from sqlalchemy import BigInteger, Column, Integer, MetaData, Sequence, String, Table, create_engine, insert, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateSequence, CreateTable

from app import business_ids as ids
from config.database import Base

EXPECTED_BUSINESS_TABLES = {
    'categories',
    'collection_runs',
    'data_sources',
    'digest_schedules',
    'generation_tasks',
    'knowledge_files',
    'model_calls',
    'news_articles',
    'papers',
    'report_assets',
    'reports',
    'templates',
}
POSTGRES_BIGINT_MAX = 2**63 - 1
JAVASCRIPT_SAFE_MAX = 2**53 - 1


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError('Numeric ID tests must never connect to external services')

    monkeypatch.setattr(socket.socket, 'connect', fail)
    monkeypatch.setattr(socket, 'create_connection', fail)


@pytest.mark.parametrize(
    'value',
    [
        1,
        '1',
        '0001',
        42,
        '42',
        JAVASCRIPT_SAFE_MAX,
        str(JAVASCRIPT_SAFE_MAX + 1),
        POSTGRES_BIGINT_MAX,
        str(POSTGRES_BIGINT_MAX),
    ],
)
def test_parse_returns_exact_positive_integer(value: int | str) -> None:
    result = ids.parse_business_id(value)
    assert type(result) is int
    assert result == int(value)


@pytest.mark.parametrize('value', [None, True, False, 1.0, Decimal('1'), b'1', [], {}, object()])
def test_parse_rejects_coercible_non_id_types(value: object) -> None:
    with pytest.raises(ValueError):
        ids.parse_business_id(value)


@pytest.mark.parametrize(
    'value',
    ['', ' ', ' 1', '1 ', '+1', '-1', '1.0', '1e3', '0x10', '1_000', '１', '١', '²', '\x001', '1\n', 'article-1'],
)
def test_parse_rejects_non_ascii_or_non_decimal_protocol_values(value: str) -> None:
    with pytest.raises(ValueError):
        ids.parse_business_id(value)


@pytest.mark.parametrize(
    'value', [0, '0', '000', -1, '-1', POSTGRES_BIGINT_MAX + 1, str(POSTGRES_BIGINT_MAX + 1), '9' * 5000]
)
def test_parse_rejects_zero_negative_and_bigint_overflow(value: int | str) -> None:
    with pytest.raises(ValueError):
        ids.parse_business_id(value)


@pytest.mark.parametrize('value', [1, '00042', JAVASCRIPT_SAFE_MAX + 1, POSTGRES_BIGINT_MAX, str(POSTGRES_BIGINT_MAX)])
def test_wire_id_uses_canonical_decimal_string_without_float_roundtrip(value: int | str) -> None:
    result = ids.wire_id(value)
    assert type(result) is str
    assert result == str(int(value))
    assert ids.parse_business_id(result) == int(value)


def test_wire_null_is_preserved_but_parse_null_is_rejected() -> None:
    assert ids.wire_id(None) is None
    with pytest.raises(ValueError):
        ids.parse_business_id(None)


@pytest.mark.parametrize('value', [True, False, '', 0, '1.5', POSTGRES_BIGINT_MAX + 1])
def test_wire_id_does_not_silently_serialize_invalid_ids(value: object) -> None:
    with pytest.raises(ValueError):
        ids.wire_id(value)


def test_business_id_scope_and_shared_sequence_contract() -> None:
    assert set(ids.BUSINESS_ID_TABLES) == EXPECTED_BUSINESS_TABLES
    assert len(ids.BUSINESS_ID_TABLES) == len(EXPECTED_BUSINESS_TABLES)
    assert not {'sys_user', 'ai_models', 'basket_items', 'report_versions'} & EXPECTED_BUSINESS_TABLES
    assert ids.MAX_BIGINT == POSTGRES_BIGINT_MAX
    assert ids.BUSINESS_ID_SEQUENCE.name == 'business_id_seq'
    assert ids.BUSINESS_ID_SEQUENCE.metadata is Base.metadata


@pytest.fixture
def private_tables(monkeypatch: pytest.MonkeyPatch) -> Generator[tuple[Table, Table]]:
    metadata = MetaData()
    # Exercise business_pk without changing the production sequence's column
    # attachment or registering test tables on Base.metadata.
    sequence = Sequence(ids.BUSINESS_ID_SEQUENCE.name, metadata=metadata)
    monkeypatch.setattr(ids, 'BUSINESS_ID_SEQUENCE', sequence)
    tables = tuple(
        Table(name, metadata, ids.business_pk(name='id', nullable=False), Column('label', String(40), nullable=False))
        for name in ('numeric_id_first', 'numeric_id_second')
    )
    yield tables
    assert not set(metadata.tables) & set(Base.metadata.tables)


def test_pk_dialect_types_and_postgresql_shared_sequence_sql(private_tables: tuple[Table, Table]) -> None:
    dialect = postgresql.dialect()
    for table in private_tables:
        column = table.c.id
        assert column.primary_key and not column.nullable
        assert isinstance(column.type.dialect_impl(dialect), BigInteger)
        assert type(column.type.dialect_impl(sqlite.dialect())) is Integer
        assert column.default is ids.BUSINESS_ID_SEQUENCE
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "id BIGINT DEFAULT nextval('business_id_seq') NOT NULL" in ddl
        assert 'PRIMARY KEY (id)' in ddl
        assert 'SERIAL' not in ddl
        statement = str(insert(table).values(label='offline').returning(table.c.id).compile(dialect=dialect))
        assert "nextval('business_id_seq')" in statement
        assert f'RETURNING {table.name}.id' in statement
    assert str(CreateSequence(ids.BUSINESS_ID_SEQUENCE).compile(dialect=dialect)) == 'CREATE SEQUENCE business_id_seq'


def test_sqlite_allocates_integer_ids_per_table_without_a_sequence_table(private_tables: tuple[Table, Table]) -> None:
    first, second = private_tables
    engine = create_engine('sqlite:///:memory:')
    try:
        first.metadata.create_all(engine)
        with engine.begin() as connection:
            first_id = connection.execute(first.insert().values(label='first')).inserted_primary_key[0]
            next_id = connection.execute(first.insert().values(label='next')).inserted_primary_key[0]
            other_table_id = connection.execute(second.insert().values(label='other')).inserted_primary_key[0]
            assert (first_id, next_id, other_table_id) == (1, 2, 1)
            assert all(type(value) is int for value in (first_id, next_id, other_table_id))
            names = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").scalars().all()
            assert 'business_id_seq' not in names
            assert connection.execute(select(first.c.id).order_by(first.c.id)).scalars().all() == [1, 2]
    finally:
        engine.dispose()


def test_postgresql_explicit_id_insert_does_not_request_a_sequence_value(private_tables: tuple[Table, Table]) -> None:
    first, _ = private_tables
    sql = str(
        insert(first)
        .values(id=POSTGRES_BIGINT_MAX, label='migrated')
        .compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True})
    )
    assert str(POSTGRES_BIGINT_MAX) in sql
    assert 'nextval' not in sql
    # Sequence synchronization after imported IDs belongs to the migration;
    # compiling an explicit-ID INSERT is not evidence that setval was applied.


def test_sqlite_preserves_explicit_bigint_and_then_allocates_after_existing_max(
    private_tables: tuple[Table, Table],
) -> None:
    first, second = private_tables
    engine = create_engine('sqlite:///:memory:')
    try:
        first.metadata.create_all(engine)
        with engine.begin() as connection:
            high_id = JAVASCRIPT_SAFE_MAX + 1
            connection.execute(first.insert().values(id=high_id, label='migrated'))
            allocated = connection.execute(first.insert().values(label='new')).inserted_primary_key[0]
            assert allocated == high_id + 1
            connection.execute(second.insert().values(id=POSTGRES_BIGINT_MAX, label='max'))
            assert connection.execute(select(second.c.id)).scalar_one() == POSTGRES_BIGINT_MAX
            assert ids.wire_id(allocated) == '9007199254740993'
    finally:
        engine.dispose()
