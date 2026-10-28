"""Beijing audit storage/formatting only; leases and publication remain absolute."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    and_,
    create_engine,
    or_,
    select,
    text,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable

from app.business_time import BeijingAuditTime, audit_as_utc, audit_now, format_business_time, server_now
from app.infrastructure.models.registry import register_sqlalchemy_models
from config.database import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect

UTC = timezone.utc
BEIJING = ZoneInfo('Asia/Shanghai')
AUDIT_FIELD_COUNT = 27
CLOCK_TOLERANCE_SECONDS = 3
SERVER_DEFAULT_ROW_ID = 2


@pytest.mark.parametrize('dialect', [postgresql.dialect(), sqlite.dialect()])
@pytest.mark.parametrize(
    'value',
    [
        datetime(2026, 10, 25, 0, 1, 2, 999999, UTC),
        datetime(2026, 10, 25, 8, 1, 2, 123456, BEIJING),
        datetime(2026, 10, 25, 8, 1, 2, 654321),
    ],
)
def test_bind_is_beijing_naive_and_floors_microseconds(dialect: Dialect, value: datetime) -> None:
    result = BeijingAuditTime().process_bind_param(value, dialect)
    assert result == datetime(2026, 10, 25, 8, 1, 2) and result.tzinfo is None


@pytest.mark.parametrize('dialect', [postgresql.dialect(), sqlite.dialect()])
def test_result_is_utc_aware_and_null_is_preserved(dialect: Dialect) -> None:
    kind = BeijingAuditTime()
    assert kind.process_result_value(datetime(2026, 10, 25, 8, 1, 2), dialect) == datetime(
        2026, 10, 25, 0, 1, 2, tzinfo=UTC
    )
    assert kind.process_bind_param(None, dialect) is None
    assert kind.process_result_value(None, dialect) is None


@pytest.mark.parametrize(
    'value',
    [
        datetime(2026, 10, 25, 0, 1, 2, 999999, UTC),
        datetime(2026, 10, 25, 8, 1, 2, 999999),
        '2026-10-25T00:01:02.999999Z',
        '2026-10-25 08:01:02',
    ],
)
def test_formatter_is_seconds_only_and_handles_naive_explicitly(value: datetime | str) -> None:
    assert format_business_time(value) == '2026-10-25 08:01:02'


def test_formatter_empty_and_day_rollover() -> None:
    assert format_business_time(None) == ''
    assert format_business_time(None, empty=None) is None
    assert format_business_time('') == ''
    assert format_business_time(datetime(2026, 10, 25, 19, 59, 59, 999999, UTC)) == '2026-10-26 03:59:59'
    assert (
        format_business_time(datetime(2026, 10, 25, 3, tzinfo=timezone(timedelta(hours=-5)))) == '2026-10-25 16:00:00'
    )


def test_default_audit_clock_is_utc_aware_floor_seconds() -> None:
    before, now, after = datetime.now(UTC), audit_now(), datetime.now(UTC)
    assert now.tzinfo is UTC and now.microsecond == 0
    assert before.replace(microsecond=0) <= now <= after


def test_pg_sql_storage_default_and_aware_literal_coercion() -> None:
    table = Table('audit', MetaData(), Column('created_at', BeijingAuditTime(), server_default=server_now()))
    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert 'TIMESTAMP(0) WITHOUT TIME ZONE' in ddl
    assert "date_trunc('second', CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Shanghai')" in ddl
    query = select(table).where(table.c.created_at == datetime(2026, 10, 25, 0, 1, 2, 999999, UTC))
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert '2026-10-25 08:01:02' in sql and '999999' not in sql and '+00:00' not in sql
    absolute = audit_as_utc(table.c.created_at)
    assert absolute.type.timezone
    assert "AT TIME ZONE 'Asia/Shanghai'" in str(absolute.compile(dialect=postgresql.dialect()))


def test_sqlite_roundtrip_python_bind_and_server_default() -> None:
    engine = create_engine('sqlite:///:memory:')
    table = Table(
        'audit',
        MetaData(),
        Column('id', Integer, primary_key=True),
        Column('created_at', BeijingAuditTime(), server_default=server_now()),
        Column('lease_expires_at', DateTime(timezone=True)),
    )
    try:
        table.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(id=1, created_at=datetime(2026, 10, 25, 0, 1, 2, 999999, UTC)))
            assert connection.scalar(text('SELECT created_at FROM audit WHERE id=1')) == '2026-10-25 08:01:02.000000'
            assert connection.scalar(select(table.c.created_at).where(table.c.id == 1)) == datetime(
                2026, 10, 25, 0, 1, 2, tzinfo=UTC
            )
            connection.execute(table.insert().values(id=SERVER_DEFAULT_ROW_ID))
            server_value = connection.scalar(select(table.c.created_at).where(table.c.id == SERVER_DEFAULT_ROW_ID))
            assert server_value.tzinfo is UTC and server_value.microsecond == 0
            assert abs((server_value - datetime.now(UTC)).total_seconds()) < CLOCK_TOLERANCE_SECONDS
    finally:
        engine.dispose()


def test_sqlite_utc_audit_cursor_same_second_equality_and_tiebreak() -> None:
    table = Table(
        'audit_cursor', MetaData(), Column('id', Integer, primary_key=True), Column('created_at', BeijingAuditTime())
    )
    anchor = datetime(2026, 10, 25, tzinfo=UTC)
    engine = create_engine('sqlite:///:memory:')
    try:
        table.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(table.insert(), [{'id': 1, 'created_at': anchor}, {'id': 2, 'created_at': anchor}])
            absolute = audit_as_utc(table.c.created_at)
            assert list(connection.scalars(select(table.c.id).where(absolute == anchor).order_by(table.c.id))) == [1, 2]
            cursor = or_(absolute < anchor, and_(absolute == anchor, table.c.id < SERVER_DEFAULT_ROW_ID))
            assert list(connection.scalars(select(table.c.id).where(cursor))) == [1]
    finally:
        engine.dispose()


def test_business_model_audit_columns_only_and_mixed_guard_compiles_both_dialects() -> None:
    register_sqlalchemy_models()
    count = 0
    for table in Base.metadata.tables.values():
        for column in table.c:
            if isinstance(column.type, BeijingAuditTime):
                assert not table.name.startswith('sys_')
                assert column.name in {'created_at', 'updated_at'} or (table.name == 'digest_schedules' and column.name == 'last_run_at')
                count += 1
    assert count == AUDIT_FIELD_COUNT + 1  # 最近派发检查同样使用北京时间秒精度。
    collection = Base.metadata.tables['collection_runs']
    assert not isinstance(collection.c.available_at.type, BeijingAuditTime)
    assert collection.c.available_at.type.timezone
    pg = str(CreateTable(collection).compile(dialect=postgresql.dialect()))
    sqlite_ddl = str(CreateTable(collection).compile(dialect=sqlite.dialect()))
    assert "created_at AT TIME ZONE 'Asia/Shanghai'" in pg
    assert "datetime(created_at, '-8 hours')" in sqlite_ddl
    assert 'AT TIME ZONE' not in sqlite_ddl


@pytest.mark.parametrize(
    'field', ['available_at', 'started_at', 'finished_at', 'stop_requested_at', 'finish_before_start']
)
def test_sqlite_actual_mixed_check_rejects_events_before_audit_instant(field: str) -> None:
    register_sqlalchemy_models()
    guard = next(
        check
        for check in Base.metadata.tables['collection_runs'].constraints
        if check.name == 'ck_collection_runs_times'
    )
    table = Table(
        'timing_guard',
        MetaData(),
        Column('created_at', BeijingAuditTime()),
        *(
            Column(name, DateTime(timezone=True))
            for name in ('available_at', 'started_at', 'finished_at', 'stop_requested_at')
        ),
        CheckConstraint(guard.sqltext, name='ck_collection_runs_times'),
    )
    anchor = datetime(2026, 10, 25, 0, 0, 0, tzinfo=UTC)
    values = {
        'created_at': anchor,
        'available_at': anchor,
        'started_at': None,
        'finished_at': None,
        'stop_requested_at': None,
    }
    engine = create_engine('sqlite:///:memory:')
    try:
        table.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(table.insert().values(**values))
            if field == 'finish_before_start':
                values.update(started_at=anchor + timedelta(seconds=2), finished_at=anchor + timedelta(seconds=1))
            else:
                values[field] = anchor - timedelta(seconds=1)
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()
