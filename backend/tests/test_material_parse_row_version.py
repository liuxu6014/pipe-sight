"""Opaque parse attempts remain distinct when audit timestamps share a second."""

# Offline fixture doubles follow the research integration tests.
# ruff: noqa: ANN001, ANN201, PLR2004

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update
from sqlalchemy.dialects import postgresql
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network
from test_research_simplified_20261025 import seed

env = memory_env
db = memory_db
no_external_network = offline_network


@pytest.mark.asyncio
async def test_same_second_requeue_reclaim_rejects_old_parse_and_preserves_user_edit(env, db, monkeypatch):
    _, row = seed(env, db)
    stamp = datetime(2026, 10, 25, 0, 1, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(env.library_repo, 'utcnow', lambda: stamp)
    row.status = 'queued'
    await db.commit()
    first = await env.library_repo.MaterialDao.claim_material_parse(db, row.id)
    first_token = first._parse_token
    assert isinstance(first_token, str) and first_token
    # This is the real service transition: editing invalidates the old parse.
    await env.materials.MaterialService.edit(
        db, 7, row.id, expected_version=1, edited_text='Keep my edit',
    )
    second = await env.library_repo.MaterialDao.claim_material_parse(db, row.id)
    second_token = second._parse_token
    assert first_token != second_token
    assert not await env.library_repo.MaterialDao.finish_material_parse(
        db, row.id, parse_token=first_token, status='ready', extracted_text='STALE',
    )
    assert await env.library_repo.MaterialDao.finish_material_parse(
        db, row.id, parse_token=second_token, status='ready', extracted_text='Fresh parse',
    )
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, row.id)
    assert current.extracted_text == 'Fresh parse' and current.edited_text == 'Keep my edit'
    assert current.version == 2 and current.status == 'ready'
    assert not await env.library_repo.MaterialDao.finish_material_parse(
        db, row.id, parse_token=second_token, status='ready', extracted_text='Duplicate completion',
    )


@pytest.mark.asyncio
async def test_same_second_raw_requeue_without_version_change_also_fences_old_attempt(env, db, monkeypatch):
    _, row = seed(env, db)
    stamp = datetime(2026, 10, 25, tzinfo=timezone.utc)
    monkeypatch.setattr(env.library_repo, 'utcnow', lambda: stamp)
    row.status = 'queued'
    await db.commit()
    first = await env.library_repo.MaterialDao.claim_material_parse(db, row.id)
    old = first._parse_token
    await db.execute(update(env.material.PipelineMaterial).where(
        env.material.PipelineMaterial.id == row.id,
    ).values(status='queued', updated_at=stamp))
    await db.commit()
    second = await env.library_repo.MaterialDao.claim_material_parse(db, row.id)
    new = second._parse_token
    assert old != new and second.version == 1
    assert not await env.library_repo.MaterialDao.finish_material_parse(
        db, row.id, parse_token=old, status='failed', extracted_text='Old worker', error='stale',
    )
    assert await env.library_repo.MaterialDao.finish_material_parse(
        db, row.id, parse_token=new, status='ready', extracted_text='New worker',
    )


@pytest.mark.asyncio
async def test_pg_claim_returns_atomic_xmin_and_never_reloads_after_commit(env):
    claimed = SimpleNamespace(id=101, updated_at=datetime.now(timezone.utc))
    result = SimpleNamespace(first=lambda: (claimed, '424242'))
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),
        execute=AsyncMock(return_value=result), commit=AsyncMock(),
        get=AsyncMock(side_effect=AssertionError('Reload could observe a later claim')),
    )
    row = await env.library_repo.MaterialDao.claim_material_parse(db, 101)
    assert row is claimed and row._parse_token == 'pg:424242'
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert 'RETURNING' in sql and 'xmin' in sql
    db.get.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_pg_finish_guards_xmin_not_timestamp(env):
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)), commit=AsyncMock(),
    )
    assert await env.library_repo.MaterialDao.finish_material_parse(
        db, 101, parse_token='pg:424242', status='ready', extracted_text='New text',
    )
    statement = db.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    where = sql.split('WHERE', 1)[1]
    assert 'xmin' in where and '424242' in where and 'parsing' in where
    assert 'updated_at' not in where and 'edited_text' not in sql and 'version=' not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize('token', [None, '', 'pg:1 OR true', 'sqlite:invalid', datetime.now(timezone.utc)])
async def test_malformed_or_timestamp_tokens_cannot_finish_parse(env, token):
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),
        execute=AsyncMock(side_effect=AssertionError('Invalid token reached UPDATE')), commit=AsyncMock(),
    )
    assert not await env.library_repo.MaterialDao.finish_material_parse(
        db, 101, parse_token=token, status='ready', extracted_text='Should not write',
    )
    db.execute.assert_not_awaited()
