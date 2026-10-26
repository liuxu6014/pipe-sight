"""Opt-in PG19432 Beijing audit fencing/cursors; all 29 table rows roll back."""

# Explicit regression data and fixture args follow the PG rehearsal suite.
# ruff: noqa: ANN001, ANN201, PLR2004

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import URL, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


async def fingerprints(connection, names):
    result = {}
    for name in sorted(names):
        assert name.replace('_', '').isalnum()
        result[name] = tuple((await connection.execute(text(
            "SELECT count(*),md5(coalesce(string_agg(h,'' ORDER BY h),'')) FROM "
            f'(SELECT md5(row_to_json(t)::text) h FROM public."{name}" t) s'
        ))).one())
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize('zone', ['UTC', 'Asia/Shanghai'])
async def test_real_pg_xmin_same_second_and_audit_search_cursors_rollback_all_rows(monkeypatch, zone):
    if os.environ.get('PIPESIGHT_TIME_PARSECAS_REHEARSE') != '1':
        pytest.skip('Explicit isolated Beijing PG19432 rehearsal opt-in required')
    from app.infrastructure.models.registry import register_sqlalchemy_models
    from app.intelligence.models.collection import PipelineSource
    from app.intelligence.models.content import PipelineArticle, PipelineCategory
    from app.library.models.materials import PipelineMaterial
    from app.library.repositories import material_repository
    from app.research.services.application import ResearchApplicationService  # noqa: F401
    from app.intelligence.services.application import IntelligenceApplicationService
    from app.schema_comments import TABLE_COMMENTS

    register_sqlalchemy_models()
    root = Path(__file__).resolve().parents[2]
    info = json.loads((root / '.runtime/schema-rollout-ythNjXpI/rehearsal-connection.json').read_text())
    assert (info['host'], int(info['port'])) == ('127.0.0.1', 19432)
    engine = create_async_engine(URL.create(
        'postgresql+asyncpg', username=info['user'], password=info['password'],
        host='127.0.0.1', port=19432, database='pipesight_beijing_initial',
    ), echo=False, hide_parameters=True, connect_args={'timeout': 5})
    # Explicit large IDs avoid nontransactional nextval calls in this rehearsal.
    base = 9223372036854700000
    marker = 'audit-cursor-' + uuid4().hex
    stamp = datetime(2026, 10, 25, 12, 0, 0, 999999, tzinfo=timezone.utc)
    monkeypatch.setattr(material_repository, 'utcnow', lambda: stamp)
    names = set(TABLE_COMMENTS)
    assert len(names) == 29
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text('SELECT current_database()')) == 'pipesight_beijing_initial'
            assert int(await connection.scalar(text('SHOW server_version_num'))) // 10000 == 18
            await connection.execute(text("SET TIME ZONE 'UTC'"))
            await connection.commit()
            before = await fingerprints(connection, names)
            await connection.rollback()
            outer = await connection.begin()
            try:
                await connection.execute(text("SET LOCAL lock_timeout='3s'"))
                await connection.execute(text("SET LOCAL statement_timeout='10s'"))
                await connection.execute(text("SELECT set_config('TimeZone', :zone, true)"), {'zone': zone})
                user = await connection.scalar(text('SELECT id FROM sys_user ORDER BY id LIMIT 1'))
                assert user is not None
                async with AsyncSession(bind=connection, expire_on_commit=False,
                                        join_transaction_mode='create_savepoint') as session:
                    row = PipelineMaterial(id=base, user_id=user, name='Parse attempt', filename='original.txt',
                        storage_key='opaque-storage-key', mime_type='text/plain', size=1, hash='1' * 64,
                        status='queued', version=1, updated_at=stamp)
                    session.add(row)
                    await session.commit()
                    first = await material_repository.MaterialDao.claim_material_parse(session, base)
                    token1 = first._parse_token
                    assert token1.startswith('pg:')
                    first.status, first.version, first.edited_text = 'queued', 2, 'User edit'
                    first.updated_at = stamp
                    await session.commit()
                    second = await material_repository.MaterialDao.claim_material_parse(session, base)
                    token2 = second._parse_token
                    assert token1 != token2
                    assert not await material_repository.MaterialDao.finish_material_parse(
                        session, base, parse_token=token1, status='ready', extracted_text='STALE',
                    )
                    assert await material_repository.MaterialDao.finish_material_parse(
                        session, base, parse_token=token2, status='ready', extracted_text='Fresh extraction',
                    )
                    await session.refresh(second)
                    assert second.edited_text == 'User edit' and second.version == 2
                    assert second.extracted_text == 'Fresh extraction'
                    raw_time = await session.scalar(text('SELECT updated_at FROM knowledge_files WHERE id=:id'), {'id': base})
                    assert raw_time == datetime(2026, 10, 25, 20)

                    session.add(PipelineCategory(id=base + 3, name=marker, prompt='test', is_enabled=False))
                    session.add(PipelineSource(id=base + 4, name=marker, type='website', adapter='manual',
                                               config={}, is_enabled=False))
                    await session.flush()
                    for identity in (base + 1, base + 2):
                        session.add(PipelineMaterial(id=identity, user_id=user, name=marker, filename='file.txt',
                            storage_key='opaque-key', mime_type='text/plain', size=1, hash=str(identity),
                            status='ready', version=1, extracted_text=marker, updated_at=stamp))
                    session.add(PipelineArticle(id=base + 5, source_id=base + 4, category_id=base + 3,
                        title=marker, content='news', url='https://example.invalid/' + marker,
                        published_at=datetime(2026, 10, 25, 15, tzinfo=timezone.utc)))
                    await session.commit()
                    params = dict(user_id=user, keyword=None, content_type='all', source='all', date_range='all',
                                  directions=marker, page_size=1)
                    seen, cursor = [], None
                    for page in (1, 2, 3):
                        result = await IntelligenceApplicationService.search_intelligence(
                            session, **params, page_num=page, cursor=cursor,
                        )
                        assert result['total'] == 3 and len(result['rows']) == 1
                        seen.append(result['rows'][0]['id'])
                        cursor = result['next_cursor']
                    assert seen == [str(base + 5), str(base + 2), str(base + 1)]
                    assert cursor is None
                    assert outer.is_active
            finally:
                await outer.rollback()
            assert await fingerprints(connection, names) == before
            await connection.rollback()
    finally:
        await engine.dispose()
