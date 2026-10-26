"""Audit wall clocks must be UTC instants in SQL, including same-second cursors."""

# Offline fixture doubles and literal datetime/ID examples are intentional.
# ruff: noqa: ANN001, ANN201, PLR2004

from datetime import datetime, timezone

import pytest
from sqlalchemy import BigInteger, Column, MetaData, Table, Text, create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, registry
from test_research_simplified_20261025 import AsyncMemory

from app.business_time import BeijingAuditTime
from app.intelligence.repositories import content_repository as repository


@pytest.fixture
def model(monkeypatch):
    mapper = registry(metadata=MetaData())
    table = Table('cursor_material', mapper.metadata,
                  Column('id', BigInteger, primary_key=True), Column('user_id', BigInteger),
                  Column('name', Text), Column('edited_text', Text), Column('extracted_text', Text),
                  Column('updated_at', BeijingAuditTime()))

    class Material:
        pass

    mapper.map_imperatively(Material, table)
    monkeypatch.setattr(repository, 'PipelineMaterial', Material)
    yield Material, mapper
    mapper.dispose()


@pytest.mark.asyncio
async def test_pg_search_sql_uses_explicit_utc_audit_expression(model):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    material, _ = model
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    await repository.ContentDao.list_search_materials(
        db, 7, ranked=True, search_after=(0, datetime(2026, 10, 25, 12, tzinfo=timezone.utc), 'document', 2),
    )
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.asyncpg.dialect()))
    assert "AT TIME ZONE 'Asia/Shanghai'" in sql
    assert 'TIMESTAMP WITH TIME ZONE' in sql
    expression = db.execute.await_args.args[0].selected_columns['_search_cursor_date']
    assert expression.type.timezone


@pytest.mark.asyncio
async def test_sqlite_equal_second_cursor_does_not_repeat_or_skip(model):
    material, mapper = model
    engine = create_engine('sqlite:///:memory:')
    mapper.metadata.create_all(engine)
    stamp = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
    try:
        with Session(engine, expire_on_commit=False) as session:
            for identity in (1, 2):
                session.add(material(id=identity, user_id=7, name='same second', updated_at=stamp))
            session.commit()
            db = AsyncMemory(session)
            first = await repository.ContentDao.list_search_materials(db, 7, ranked=True, limit=1)
            assert [row.id for row in first] == [2]
            cursor_date = first[0]._search_cursor_date
            if cursor_date.tzinfo is None:
                cursor_date = cursor_date.replace(tzinfo=timezone.utc)
            assert cursor_date == stamp
            second = await repository.ContentDao.list_search_materials(
                db, 7, ranked=True, limit=1, search_after=(0, cursor_date, 'document', 2),
            )
            assert [row.id for row in second] == [1]
    finally:
        engine.dispose()
