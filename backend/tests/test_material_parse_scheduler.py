"""资料专属队列：恢复、去重派发、扫描门和解析 CAS，不连接真实数据库。"""

import asyncio
import importlib
from datetime import timedelta
from types import SimpleNamespace as NS

import pytest
from sqlalchemy.orm import Session
from test_research_simplified_20261025 import AsyncMemory, seed
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_network

env = refactor_env
db = refactor_db
no_external_network = refactor_network


def scheduler_context(env, db, monkeypatch):
    module = importlib.import_module('app.library.tasks.material_parse_scheduler')

    def factory():
        return AsyncMemory(Session(db.s.bind, expire_on_commit=False))

    monkeypatch.setattr(module, 'AsyncSessionLocal', factory)
    module._material_tasks.clear()
    return module


@pytest.mark.asyncio
async def test_recover_dispatches_once_and_forgets_finished_tasks(env, db, monkeypatch):
    _, row = seed(env, db)
    row.status = 'queued'
    other = env.material.PipelineMaterial(
        id=102,
        user_id=7,
        name='第二份',
        filename='second.txt',
        storage_key='second.txt',
        mime_type='text/plain',
        size=1,
        hash='b' * 64,
        status='queued',
        version=1,
    )
    db.add(other)
    await db.commit()
    scheduler = scheduler_context(env, db, monkeypatch)
    calls = []

    async def process(material_id, worker_id=''):
        calls.append(material_id)

    monkeypatch.setattr(scheduler, 'process_material_parse', process)
    first = await scheduler.recover_material_parses()
    second = await scheduler.recover_material_parses()
    assert first == {'found': 2, 'dispatched': 2} and second == {'found': 2, 'dispatched': 0}
    await asyncio.gather(*list(scheduler._material_tasks.values()))
    await asyncio.sleep(0)
    assert sorted(calls) == [101, 102] and scheduler._material_tasks == {}


@pytest.mark.asyncio
async def test_recovery_requeues_expired_parse_before_dispatch(env, db, monkeypatch):
    _, row = seed(env, db)
    row.status = 'parsing'
    row.updated_at = env.material.utcnow() - timedelta(minutes=16)
    await db.commit()
    scheduler = scheduler_context(env, db, monkeypatch)
    calls = []

    async def process(material_id, worker_id=''):
        calls.append(material_id)

    monkeypatch.setattr(scheduler, 'process_material_parse', process)
    result = await scheduler.recover_material_parses()
    await asyncio.gather(*list(scheduler._material_tasks.values()))
    await asyncio.sleep(0)
    db.s.expire_all()
    assert result == {'found': 1, 'dispatched': 1}
    assert (await db.get(env.material.PipelineMaterial, 101)).status == 'queued' and calls == [101]


@pytest.mark.asyncio
async def test_worker_parses_original_filename_and_preserves_edited_text(env, db, tmp_path, monkeypatch):
    _, row = seed(env, db)
    row.status = 'queued'
    row.edited_text = '用户编辑正文'
    row.name = '用户改名后没有后缀'
    await db.commit()
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    (tmp_path / 'a.txt').write_text('本次系统提取正文', encoding='utf-8')
    scheduler = scheduler_context(env, db, monkeypatch)
    monkeypatch.setattr(scheduler.FileScanService, 'scan', lambda *_: NS(status='clean'))
    await scheduler.process_material_parse('101')
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.status == 'ready' and current.extracted_text == '本次系统提取正文'
    assert current.edited_text == '用户编辑正文' and current.version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['pending', 'quarantined', 'failed'])
async def test_worker_never_parses_or_marks_ready_before_clean_scan(env, db, tmp_path, monkeypatch, status):
    _, row = seed(env, db)
    row.status = 'queued'
    row.edited_text = '用户编辑正文'
    await db.commit()
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    (tmp_path / 'a.txt').write_text('原始正文')
    scheduler = scheduler_context(env, db, monkeypatch)
    monkeypatch.setattr(scheduler.FileScanService, 'scan', lambda *_: NS(status=status))

    def forbidden(*args, **kwargs):
        raise AssertionError('unscanned file reached parser')

    monkeypatch.setattr(scheduler.MaterialFileService, 'parse', forbidden)
    await scheduler.process_material_parse('101')
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.status == 'failed' and '安全扫描' in current.error
    assert current.edited_text == '用户编辑正文'


@pytest.mark.asyncio
async def test_stop_cancels_inflight_tasks(env):
    scheduler = importlib.import_module('app.library.tasks.material_parse_scheduler')
    started, release = asyncio.Event(), asyncio.Event()

    async def pending():
        started.set()
        await release.wait()

    task = asyncio.create_task(pending())
    await started.wait()
    scheduler._material_tasks['101'] = task
    try:
        await scheduler.stop_material_parse_tasks()
        assert task.cancelled() and scheduler._material_tasks == {}
    finally:
        release.set()
