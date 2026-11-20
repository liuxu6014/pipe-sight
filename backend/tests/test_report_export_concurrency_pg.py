"""Independent PG connections serialize export creation in a disposable schema.

Uses the existing labelled-local report rehearsal opt-in, never app settings.
All fixture rows and sequences live in a unique schema, which is removed in
finally; the rehearsal database's public tables are not modified.
"""

import asyncio
import importlib
import os
import socket
from uuid import uuid4

import pytest
from pg_rehearsal import connection_info
from sqlalchemy import URL, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from test_research_simplified_20261025 import env as offline_env

env = offline_env


@pytest.mark.asyncio
async def test_separate_pg_connections_reuse_one_pending_export_under_the_report_row_lock(env, monkeypatch):
    if os.environ.get('PIPESIGHT_REPORT_METADATA_PG') != '1':
        pytest.skip('Explicit isolated local report PostgreSQL rehearsal opt-in required')
    info = connection_info()
    assert (info['host'], int(info['port'])) == ('127.0.0.1', 19432)
    original_connect = socket.socket.connect

    def local_only(sock, address):
        assert address[0] == '127.0.0.1' and address[1] == 19432, 'Export rehearsal reached a nonlocal service'
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', local_only)
    schema = 'export_reuse_' + uuid4().hex
    engine = create_async_engine(
        URL.create(
            'postgresql+asyncpg',
            username=info['user'],
            password=info['password'],
            host=info['host'],
            port=info['port'],
            database=info['dbname'],
        ),
        hide_parameters=True,
        connect_args={'timeout': 5, 'server_settings': {'lock_timeout': '5s', 'statement_timeout': '10s'}},
        execution_options={'schema_translate_map': {None: schema}},
    )
    exports = importlib.import_module('app.research.services.exports')
    added, release = asyncio.Event(), asyncio.Event()
    add = env.repo.ResearchDao.add_report_export
    add_count = 0

    async def gated_add(db, row):
        nonlocal add_count
        add_count += 1
        if add_count == 1:
            added.set()
            await release.wait()
        return await add(db, row)

    monkeypatch.setattr(env.repo.ResearchDao, 'add_report_export', gated_add)
    tasks = []
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(env.Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await db.execute(env.Base.metadata.tables['sys_user'].insert().values(id=7))
            db.add(
                env.models.PipelineReport(
                    id=301, user_id=7, title='并发导出', type='research', content='冻结正文', version=1
                )
            )
            await db.commit()

        async def create():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                return await exports.ResearchReportExportService.create(db, user_id=7, report_id=301, file_format='pdf')

        tasks.append(asyncio.create_task(create()))
        await asyncio.wait_for(added.wait(), 5)
        tasks.append(asyncio.create_task(create()))

        async def wait_for_database_lock():
            while True:
                async with engine.connect() as connection:
                    count = await connection.scalar(
                        text(
                            'SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                            "AND wait_event_type='Lock' AND query LIKE :pattern"
                        ),
                        {'pattern': f'%{schema}%FOR UPDATE%'},
                    )
                if count:
                    return
                if tasks[1].done():
                    pytest.fail('Second export bypassed the report lock while the first create was pending')
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_database_lock(), 3)
        assert not tasks[1].done()
        release.set()
        first, second = await asyncio.wait_for(asyncio.gather(*tasks), 5)
        assert first['exportId'] == second['exportId'] and add_count == 1
        async with AsyncSession(engine, expire_on_commit=False) as db:
            assert await db.scalar(select(func.count()).select_from(env.models.PipelineReportAsset)) == 1
            row = await db.scalar(select(env.models.PipelineReportAsset))
            assert row.config_snapshot['report']['content'] == '冻结正文'
            assert row.id == await db.scalar(text(f'SELECT last_value FROM "{schema}".business_id_seq'))
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
