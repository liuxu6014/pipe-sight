"""Opt-in PG18 regressions; isolated rehearsal only, every insert rolled back.

Run after coordinating the PG19432 window with the migration owner:
PIPESIGHT_PAGINATION_PG_REHEARSE=1 PYTHONPATH=src:. .venv/bin/python -m pytest \
    -q tests/test_content_pagination_pg_regression.py
The configured application database and .env credentials are never used here.
"""

import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import URL, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.intelligence.models.collection import PipelineSource
from app.intelligence.models.content import PipelineArticle, PipelineCategory, PipelinePaper
from app.intelligence.services.application import IntelligenceApplicationService

EXPECTED_TOTAL = 2
EXPECTED_PG_MAJOR = 18
REHEARSAL_ROOT = Path(__file__).resolve().parents[2] / '.runtime/schema-rollout-ythNjXpI'
CONTAINER = 'pipesight-schema-rehearsal-ythnjxpi'


@pytest_asyncio.fixture(params=['UTC', 'Asia/Shanghai'])
async def rehearsal(request: pytest.FixtureRequest) -> AsyncIterator[tuple[AsyncSession, str, int, int]]:
    if os.environ.get('PIPESIGHT_PAGINATION_PG_REHEARSE') != '1':
        pytest.skip('Explicit PG19432 pagination regression opt-in required')
    info = json.loads((REHEARSAL_ROOT / 'rehearsal-connection.json').read_text())
    assert (info['host'], int(info['port']), info['dbname']) == (
        '127.0.0.1',
        19432,
        'pipesight_rehearsal',
    )
    # Inspect only labels/ports, never container Env or credentials.
    labels = await asyncio.to_thread(
        subprocess.run,
        ['docker', 'inspect', '--format', '{{json .Config.Labels}}', CONTAINER],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(labels.stdout)['pipesight.schema-rollout'] == 'ythNjXpI'
    ports = await asyncio.to_thread(
        subprocess.run,
        ['docker', 'inspect', '--format', '{{json .NetworkSettings.Ports}}', CONTAINER],
        check=True,
        capture_output=True,
        text=True,
    )
    assert {'HostIp': '127.0.0.1', 'HostPort': '19432'} in json.loads(ports.stdout)['5432/tcp']
    engine = create_async_engine(
        URL.create(
            'postgresql+asyncpg',
            username=info['user'],
            password=info['password'],
            host='127.0.0.1',
            port=19432,
            database='pipesight_rehearsal',
        ),
        echo=False,
        hide_parameters=True,
        connect_args={'timeout': 5},
    )
    marker = 'pagination-' + uuid4().hex
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                assert await connection.scalar(text('SELECT current_database()')) == 'pipesight_rehearsal'
                version = int(await connection.scalar(text('SHOW server_version_num')))
                assert version // 10000 == EXPECTED_PG_MAJOR
                await connection.execute(text("SET LOCAL statement_timeout='10s'"))
                await connection.execute(text("SET LOCAL lock_timeout='3s'"))
                await connection.execute(text("SELECT set_config('TimeZone', :zone, true)"), {'zone': request.param})
                # Hold ordinary table locks through rollback so a coordinated
                # rebuild cannot drop the tables in the middle of these reads.
                await connection.execute(
                    text('LOCK TABLE categories,data_sources,news_articles,papers IN ROW EXCLUSIVE MODE')
                )
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    category = PipelineCategory(
                        name=marker,
                        prompt='Regression fixture',
                        applies_to='all',
                        is_enabled=False,
                    )
                    source = PipelineSource(
                        name=marker,
                        type='website',
                        adapter='manual',
                        is_enabled=False,
                        config={},
                    )
                    session.add_all([category, source])
                    await session.flush()
                    source_id, category_id = source.id, category.id
                    yield session, marker, source_id, category_id
            finally:
                await transaction.rollback()
            # Prove test rows did not survive, without deleting any rows.
            for model, identity in ((PipelineCategory, category_id), (PipelineSource, source_id)):
                assert await connection.scalar(select(func.count()).select_from(model).where(model.id == identity)) == 0
            for model in (PipelineArticle, PipelinePaper):
                assert (
                    await connection.scalar(
                        select(func.count()).select_from(model).where(model.category_id == category_id)
                    )
                    == 0
                )
            await connection.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_keyword_catalog_pages_do_not_repeat_ranked_candidate(
    rehearsal: tuple[AsyncSession, str, int, int],
) -> None:
    db, marker, source_id, category_id = rehearsal
    fixtures = [
        PipelineArticle(
            source_id=source_id,
            category_id=category_id,
            title=marker + ' title match',
            content='Older body',
            url='https://example.test/' + marker + '-old',
            published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        ),
        PipelineArticle(
            source_id=source_id,
            category_id=category_id,
            title='Recent news',
            content=marker + ' body match',
            url='https://example.test/' + marker + '-new',
            published_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        ),
    ]
    db.add_all(fixtures)
    await db.flush()
    old_id, new_id = (str(row.id) for row in fixtures)
    ids = []
    for page in (1, 2):
        result = await IntelligenceApplicationService.list_intelligence(
            db,
            category='news',
            keyword=marker,
            source_type=None,
            page_num=page,
            page_size=1,
        )
        assert result['total'] == EXPECTED_TOTAL
        ids.extend(row['id'] for row in result['rows'])
    assert ids == [new_id, old_id]
    assert len(set(ids)) == EXPECTED_TOTAL
    # Search must retain relevance ranking when catalog uses publication order.
    result = await IntelligenceApplicationService.search_intelligence(
        db,
        user_id=42,
        keyword=marker,
        content_type='news',
        source='public',
        date_range='all',
        directions=None,
        page_num=1,
        page_size=1,
    )
    assert result['total'] == EXPECTED_TOTAL
    assert [row['id'] for row in result['rows']] == [old_id]


@pytest.mark.asyncio
async def test_news_noon_cursor_keeps_same_day_paper_at_utc_midnight(
    rehearsal: tuple[AsyncSession, str, int, int],
) -> None:
    db, marker, source_id, category_id = rehearsal
    fixtures = [
        PipelineArticle(
            source_id=source_id,
            category_id=category_id,
            title='News at noon UTC',
            content='News body',
            url='https://example.test/' + marker + '-news',
            published_at=datetime(2026, 10, 2, 12, tzinfo=timezone.utc),
        ),
        PipelinePaper(
            category_id=category_id,
            title='Paper on the same day',
            published_date='2026-10-02',
            abstract='Abstract only',
            url='https://example.test/' + marker + '-paper',
        ),
    ]
    db.add_all(fixtures)
    await db.flush()
    article_id, paper_id = (str(row.id) for row in fixtures)
    params = {
        'user_id': 42,
        'keyword': None,
        'content_type': 'all',
        'source': 'public',
        'date_range': 'all',
        'directions': marker,
        'page_size': 1,
    }
    first = await IntelligenceApplicationService.search_intelligence(db, **params, page_num=1)
    assert first['total'] == EXPECTED_TOTAL
    assert [row['id'] for row in first['rows']] == [article_id]
    assert first['next_cursor']
    second = await IntelligenceApplicationService.search_intelligence(
        db,
        **params,
        page_num=2,
        cursor=first['next_cursor'],
    )
    assert second['total'] == EXPECTED_TOTAL
    assert [row['id'] for row in second['rows']] == [paper_id]
    assert second['rows'][0]['published_at'] == '2026-10-02'
    assert second['next_cursor'] is None
