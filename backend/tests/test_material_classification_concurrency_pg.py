"""API edits/deletes and paid classification claims share real PostgreSQL row locks.

All data lives in a disposable schema on the labelled-local rehearsal database;
no application settings, files or model endpoints are used.
"""

import asyncio
import importlib
import os
import socket
from uuid import uuid4

import pytest
from pg_rehearsal import connection_info
from sqlalchemy import URL, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from test_research_simplified_20261025 import env as offline_env

env = offline_env


@pytest.fixture
async def local_classification_engine(env, monkeypatch, tmp_path):
    if os.environ.get('PIPESIGHT_REPORT_METADATA_PG') != '1':
        pytest.skip('Explicit isolated local report PostgreSQL rehearsal opt-in required')
    info = connection_info()
    assert (info['host'], int(info['port'])) == ('127.0.0.1', 19432)
    original_connect = socket.socket.connect

    def local_only(sock, address):
        assert address[0] == '127.0.0.1' and address[1] == 19432
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', local_only)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    schema = 'classification_lock_' + uuid4().hex
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
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.run_sync(env.Base.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await db.execute(env.Base.metadata.tables['sys_user'].insert().values(id=7))
            db.add(
                env.material.PipelineMaterial(
                    id=101,
                    user_id=7,
                    name='合成资料',
                    filename='synthetic.txt',
                    storage_key='synthetic.txt',
                    mime_type='text/plain',
                    hash='synthetic',
                    size=1,
                    status='ready',
                    classification_status='queued',
                    classification_token='consented',
                    extracted_text='合成正文',
                )
            )
            await db.commit()
        yield engine, schema
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()


async def wait_for_material_lock(engine, schema, task):
    while True:
        async with engine.connect() as connection:
            waiting = await connection.scalar(
                text(
                    'SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() '
                    "AND wait_event_type='Lock' AND query LIKE :pattern"
                ),
                {'pattern': f'%{schema}%knowledge_files%'},
            )
        if waiting:
            return
        if task.done():
            pytest.fail('Concurrent mutation bypassed the classification row lock')
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['delete', 'edit', 'reparse'])
@pytest.mark.parametrize('first_actor', ['claim', 'api'])
async def test_classification_and_api_mutations_cannot_overwrite_each_others_capacity(
    env,
    local_classification_engine,
    monkeypatch,
    operation,
    first_actor,
):
    engine, schema = local_classification_engine
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    dao = importlib.import_module('app.library.repositories.material_repository').MaterialDao
    locked, release = asyncio.Event(), asyncio.Event()
    original_owned = dao.get_owned_material

    async def gated_owned(db, *args, **kwargs):
        row = await original_owned(db, *args, **kwargs)
        if first_actor == 'api':
            locked.set()
            await release.wait()
        return row

    monkeypatch.setattr(dao, 'get_owned_material', gated_owned)

    class ClaimSession(AsyncSession):
        async def commit(self) -> None:
            if first_actor == 'claim':
                locked.set()
                await release.wait()
            await super().commit()

    async def claim():
        async with ClaimSession(engine, expire_on_commit=False) as db:
            return await repo.claim(db, 101)

    async def mutate():
        async with AsyncSession(engine, expire_on_commit=False) as db:
            try:
                if operation == 'delete':
                    return await env.materials.MaterialService.delete_material(db, 7, 101)
                if operation == 'reparse':
                    return await env.materials.MaterialService.retry_parse(db, 7, 101)
                return await env.materials.MaterialService.edit(
                    db,
                    7,
                    101,
                    expected_version=1,
                    edited_text='最新修订正文',
                )
            except env.exc as error:
                return error

    tasks = []
    try:
        tasks.append(asyncio.create_task(claim() if first_actor == 'claim' else mutate()))
        await asyncio.wait_for(locked.wait(), 3)
        tasks.append(asyncio.create_task(mutate() if first_actor == 'claim' else claim()))
        await asyncio.wait_for(wait_for_material_lock(engine, schema, tasks[1]), 3)
        assert not tasks[1].done()
        release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks), 5)
        claimed, result = results if first_actor == 'claim' else list(reversed(results))
        async with AsyncSession(engine, expire_on_commit=False) as db:
            row = await db.scalar(select(env.material.PipelineMaterial).where(env.material.PipelineMaterial.id == 101))
        if first_actor == 'claim':
            assert claimed and row.classification_status == 'running' and row.classification_token == claimed[0]
            if operation == 'delete':
                assert isinstance(result, env.exc) and '等待本次执行结束' in result.message
            elif operation == 'edit':
                assert row.version == 2 and row.edited_text == '最新修订正文'
            else:
                assert row.status == 'queued'
        elif operation == 'edit':
            assert claimed is None
            assert row.version == 2 and row.edited_text == '最新修订正文'
            assert row.classification_status == 'not_configured' and row.classification_token is None
        else:
            assert claimed is None
            assert row is None if operation == 'delete' else row.status == 'queued'
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
