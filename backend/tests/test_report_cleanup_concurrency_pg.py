"""An independent sweeper must wait for deletion commit before removing bytes."""

import asyncio
import importlib
import os
import socket
from uuid import uuid4

import pytest
from pg_rehearsal import connection_info
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from test_research_simplified_20261025 import env as offline_env

env = offline_env


@pytest.mark.asyncio
@pytest.mark.parametrize('rollback', [False, True])
async def test_cleanup_waits_for_asset_transaction_and_preserves_rollback(env, monkeypatch, tmp_path, rollback):
    if os.environ.get('PIPESIGHT_REPORT_METADATA_PG') != '1':
        pytest.skip('Explicit isolated local report PostgreSQL rehearsal opt-in required')
    info = connection_info()
    assert (info['host'], int(info['port'])) == ('127.0.0.1', 19432)
    original_connect = socket.socket.connect

    def local_only(sock, address):
        assert address[0] == '127.0.0.1' and address[1] == 19432, 'Cleanup rehearsal reached a nonlocal service'
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', local_only)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    schema = 'export_cleanup_' + uuid4().hex
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
    reports = importlib.import_module('app.research.services.reports')
    scheduler = importlib.import_module('app.research.tasks.research_job_scheduler')
    storage = reports.ReportExportStorage
    key = storage.build_key('401', 'pdf', 2026, 11, 20)
    storage.write(key, b'synthetic report')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', lambda: AsyncSession(engine, expire_on_commit=False))
    marked, release = asyncio.Event(), asyncio.Event()
    tasks = []
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(env.Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await db.execute(env.Base.metadata.tables['sys_user'].insert().values(id=7))
            db.add(env.models.PipelineReport(id=301, user_id=7, title='删除并发', type='research', content='正文'))
            await db.flush()
            db.add(
                env.models.PipelineReportAsset(
                    id=401,
                    report_id=301,
                    type='export',
                    mime_type='application/pdf',
                    storage_key=key,
                    status='completed',
                )
            )
            await db.commit()

        async def deleting():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                commit = db.commit

                async def gated_commit():
                    marked.set()
                    await release.wait()
                    if rollback:
                        await db.rollback()
                        raise RuntimeError('simulated rollback')
                    await commit()

                monkeypatch.setattr(db, 'commit', gated_commit)
                return await reports.ResearchReportService.delete_report(db, user_id=7, report_id=301)

        tasks.append(asyncio.create_task(deleting()))
        await asyncio.wait_for(marked.wait(), 5)
        assert storage._resolve(storage.cleanup_marker(key)).is_file()
        tasks.append(asyncio.create_task(scheduler.clean_deleted_report_files()))

        async def wait_for_sweeper_lock():
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
                    pytest.fail('Sweeper bypassed the live asset lock before deletion committed')
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_sweeper_lock(), 3)
        assert storage.read(key) == b'synthetic report'
        release.set()
        if rollback:
            with pytest.raises(RuntimeError, match='simulated rollback'):
                await asyncio.wait_for(tasks[0], 5)
        else:
            assert (await asyncio.wait_for(tasks[0], 5)) == {'id': '301'}
        await asyncio.wait_for(tasks[1], 5)
        assert storage._resolve(key).exists() is rollback
        assert not list(storage.cleanup_directory().iterdir())
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()
