"""Real document-classification state transitions with isolated SQL and model doubles."""

import asyncio
import importlib
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session
from test_research_simplified_20261025 import AsyncMemory, seed
from test_research_simplified_20261025 import db as memory_db
from test_research_simplified_20261025 import env as memory_env
from test_research_simplified_20261025 import no_external_network as offline_network

env, db, no_external_network = memory_env, memory_db, offline_network


async def configured(env, db):
    _, row = seed(env, db)
    row.extracted_text = '原文证据：管道腐蚀检测取得验证结果。'
    row.classification_status = 'queued'
    row.classification_token = 'consented'
    db.add(env.SysConfig(key='pipeline.processing.modelId', value='1'))
    for identity, kind, enabled in [(801, 'document', True), (802, 'paper', True), (803, 'all', False)]:
        db.add(
            env.material.PipelineCategory(
                id=identity,
                name=f'类别{identity}',
                prompt='按管道腐蚀检测分类',
                applies_to=kind,
                is_enabled=enabled,
                model_id=1,
            )
        )
    await db.commit()
    return row


@pytest.mark.asyncio
async def test_one_real_call_uses_applicable_prompt_rules_and_requires_original_evidence(env, db):
    row = await configured(env, db)
    service = importlib.import_module('app.library.services.classification').MaterialClassificationService
    calls = []

    async def gateway(_db, snapshot, **kwargs):
        calls.append((snapshot, kwargs))
        return json.dumps({'categoryId': '801', 'categoryName': '类别801', 'evidence': '管道腐蚀检测取得验证结果'})

    assert await service.classify(
        db, title=row.name, content=row.extracted_text, request_id='test-only', gateway=gateway
    ) == ('completed', 801, None)
    assert len(calls) == 1 and calls[0][0]['id'] == 1
    assert '类别801' in calls[0][1]['system_prompt'] and '类别802' not in calls[0][1]['system_prompt']
    assert '类别803' not in calls[0][1]['system_prompt']
    assert json.loads(calls[0][1]['prompt'])['content'] == row.extracted_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'answer',
    [
        {},
        {'categoryId': '999', 'categoryName': '创造类别', 'evidence': '管道腐蚀检测'},
        {'categoryId': '801', 'categoryName': '类别801', 'evidence': '原文没有的依据'},
        {'categoryId': None, 'categoryName': '类别801', 'evidence': ''},
        {'categoryId': None, 'categoryName': None, 'evidence': '虚构结论'},
    ],
)
async def test_invalid_model_classification_never_creates_a_category(env, db, answer):
    row = await configured(env, db)
    service = importlib.import_module('app.library.services.classification').MaterialClassificationService

    async def gateway(*args, **kwargs):
        return json.dumps(answer)

    with pytest.raises(env.exc) as raised:
        await service.classify(db, title=row.name, content=row.extracted_text, request_id='test-only', gateway=gateway)
    assert '正文证据' in raised.value.message


@pytest.mark.asyncio
async def test_old_files_are_not_automatically_queued_and_unconfigured_rules_make_no_call(env, db):
    _, row = seed(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    service = importlib.import_module('app.library.services.classification').MaterialClassificationService
    assert row.classification_status == 'not_configured' and await repo.ready(db) == []

    async def forbidden(*args, **kwargs):
        raise AssertionError('No paid call without configured rules')

    result = await service.classify(db, title=row.name, content='正文', request_id='test-only', gateway=forbidden)
    assert result[0] == 'not_configured' and result[1] is None


@pytest.mark.asyncio
async def test_unmatched_result_and_large_content_never_create_fake_categories(env, db):
    row = await configured(env, db)
    service = importlib.import_module('app.library.services.classification').MaterialClassificationService
    calls = []

    async def unmatched(*args, **kwargs):
        calls.append(kwargs)
        return json.dumps({'categoryId': None, 'categoryName': None, 'evidence': ''})

    assert await service.classify(
        db, title=row.name, content=row.extracted_text, request_id='none', gateway=unmatched
    ) == ('completed', None, None)
    with pytest.raises(env.exc) as rejected:
        await service.classify(db, title=row.name, content='长正文' * 10_000, request_id='long', gateway=unmatched)
    assert '超过' in rejected.value.message and len(calls) == 1


@pytest.mark.asyncio
async def test_category_options_include_all_owned_pages_but_not_other_users(env, db):
    row = await configured(env, db)
    row.category_id = 801
    db.add(
        env.material.PipelineMaterial(
            id=102,
            user_id=8,
            name='私有资料',
            filename='x.txt',
            storage_key='x.txt',
            mime_type='text/plain',
            hash='x',
            size=1,
            status='ready',
            category_id=802,
        )
    )
    await db.commit()
    assert await env.materials.MaterialService.category_options(db, 7) == {'rows': ['类别801'], 'total': 1}
    assert await env.materials.MaterialService.category_options(db, 8) == {'rows': ['类别802'], 'total': 1}


@pytest.mark.asyncio
async def test_rule_change_during_model_call_rejects_stale_classification(env, db):
    row = await configured(env, db)
    service = importlib.import_module('app.library.services.classification').MaterialClassificationService

    async def gateway(*args, **kwargs):
        category = await db.get(env.material.PipelineCategory, 801)
        category.prompt = '管理员的新规则'
        await db.commit()
        return json.dumps({'categoryId': '801', 'categoryName': '类别801', 'evidence': '管道腐蚀检测'})

    with pytest.raises(env.exc) as changed:
        await service.classify(db, title=row.name, content=row.extracted_text, request_id='changed', gateway=gateway)
    assert '规则已变化' in changed.value.message


@pytest.mark.asyncio
async def test_category_disabled_before_result_save_becomes_retryable_failure(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    claim = await repo.claim(db, 101)
    category = await db.get(env.material.PipelineCategory, 801)
    category.is_enabled = False
    await db.commit()
    assert await repo.finish(db, 101, token=claim[0], status='completed', category_id=801)
    db.s.expire_all()
    row = await db.get(env.material.PipelineMaterial, 101)
    assert (
        row.category_id is None and row.classification_status == 'failed' and '规则已变化' in row.classification_error
    )


@pytest.mark.asyncio
async def test_capacity_claims_are_bounded_and_edit_fences_old_classification(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    for identity in [102, 103]:
        db.add(
            env.material.PipelineMaterial(
                id=identity,
                user_id=7,
                name='资料',
                filename='b.txt',
                storage_key='b.txt',
                mime_type='text/plain',
                hash=str(identity),
                size=1,
                status='ready',
                classification_status='queued',
                classification_token='consented',
            )
        )
    await db.commit()
    first, second = await repo.claim(db, 101), await repo.claim(db, 102)
    assert first and second and await repo.claim(db, 103) is None
    assert await repo.claim(db, 101) is None
    with pytest.raises(env.exc) as denied:
        await env.materials.MaterialService.retry_classification(db, 8, 101)
    assert '无权' in denied.value.message
    await env.materials.MaterialService.edit(db, 7, 101, expected_version=1, edited_text='作者修订正文')
    assert await repo.claim(db, 103) is None  # The old in-flight call still owns this slot.
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.classification_status == 'running' and current.classification_token == first[0]
    assert not await repo.finish(db, 101, token=first[0], status='completed', category_id=801)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.edited_text == '作者修订正文' and current.category_id is None
    assert current.classification_status == 'not_configured' and current.classification_token is None
    assert await repo.claim(db, 103)


@pytest.mark.asyncio
async def test_interrupted_paid_classification_requires_explicit_retry(env, db):
    row = await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    claim = await repo.claim(db, 101)
    db.s.expire_all()
    row = await db.get(env.material.PipelineMaterial, 101)
    row.classification_updated_at = env.material.utcnow() - timedelta(minutes=16)
    await db.commit()
    assert await repo.ready(db) == []
    db.s.expire_all()
    row = await db.get(env.material.PipelineMaterial, 101)
    assert row.classification_status == 'failed' and '手动重试' in row.classification_error
    assert not await repo.finish(db, 101, token=claim[0], status='completed', category_id=801)
    response = await env.materials.MaterialService.retry_classification(db, 7, 101)
    assert response['classificationStatus'] == 'queued' and response['parseStatus'] == 'ready'


@pytest.mark.asyncio
async def test_worker_classifies_edited_text_after_scan_without_reparsing(env, db, tmp_path, monkeypatch):
    row = await configured(env, db)
    row.edited_text = '作者修订正文：管道腐蚀检测取得验证结果。'
    await db.commit()
    (tmp_path / 'a.txt').write_text('旧原始文件')
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    scheduler = importlib.import_module('app.library.tasks.material_parse_scheduler')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', lambda: AsyncMemory(Session(db.s.bind, expire_on_commit=False)))
    monkeypatch.setattr(scheduler.FileScanService, 'scan', lambda *_: SimpleNamespace(status='clean'))
    calls = []

    async def classify(_db, **kwargs):
        calls.append(kwargs)
        return 'completed', 801, None

    monkeypatch.setattr(scheduler.MaterialClassificationService, 'classify', classify)
    await scheduler.process_material_classification(101)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.category_id == 801 and current.classification_status == 'completed'
    assert current.edited_text.startswith('作者修订正文') and calls[0]['content'] == current.edited_text
    assert 'classification_token' not in env.materials.MaterialService.material_dict(current, 7)


@pytest.mark.asyncio
async def test_worker_never_sends_unscanned_material_to_model(env, db, tmp_path, monkeypatch):
    await configured(env, db)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    scheduler = importlib.import_module('app.library.tasks.material_parse_scheduler')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', lambda: AsyncMemory(Session(db.s.bind, expire_on_commit=False)))
    monkeypatch.setattr(scheduler.FileScanService, 'scan', lambda *_: SimpleNamespace(status='quarantined'))

    async def forbidden(*args, **kwargs):
        raise AssertionError('Unscanned text sent to model')

    monkeypatch.setattr(scheduler.MaterialClassificationService, 'classify', forbidden)
    await scheduler.process_material_classification(101)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.classification_status == 'failed' and '安全扫描' in current.classification_error
    assert current.status == 'ready' and current.category_id is None


@pytest.mark.asyncio
async def test_edits_do_not_free_capacity_while_provider_calls_are_still_in_flight(env, db, tmp_path, monkeypatch):
    await configured(env, db)
    for identity in [102, 103, 104]:
        db.add(
            env.material.PipelineMaterial(
                id=identity,
                user_id=7,
                name='合成资料',
                filename='a.txt',
                storage_key='a.txt',
                mime_type='text/plain',
                hash=str(identity),
                size=1,
                status='ready',
                classification_status='queued',
                classification_token='consented',
                extracted_text='合成正文',
            )
        )
    await db.commit()
    (tmp_path / 'a.txt').write_text('合成原件')
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    scheduler = importlib.import_module('app.library.tasks.material_parse_scheduler')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', lambda: AsyncMemory(Session(db.s.bind, expire_on_commit=False)))
    monkeypatch.setattr(scheduler.FileScanService, 'scan', lambda *_: SimpleNamespace(status='clean'))
    active, peak = 0, 0
    release = asyncio.Event()

    async def classify(_db, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await release.wait()
            return 'completed', 801, None
        finally:
            active -= 1

    monkeypatch.setattr(scheduler.MaterialClassificationService, 'classify', classify)
    tasks = [asyncio.create_task(scheduler.process_material_classification(i)) for i in [101, 102]]
    try:
        for _ in range(100):
            if active == 2:
                break
            await asyncio.sleep(0.001)
        assert active == 2
        for identity in [101, 102]:
            await env.materials.MaterialService.edit(db, 7, identity, expected_version=1, edited_text='作者的新正文')
        await asyncio.gather(*(scheduler.process_material_classification(i) for i in [103, 104]))
        assert active == 2 and peak == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)
    db.s.expire_all()
    for identity in [101, 102]:
        row = await db.get(env.material.PipelineMaterial, identity)
        assert row.edited_text == '作者的新正文' and row.category_id is None
        assert row.classification_status == 'not_configured' and row.classification_token is None


@pytest.mark.asyncio
async def test_reparse_waits_for_old_paid_classification_before_claiming_parser(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    material_repo = importlib.import_module('app.library.repositories.material_repository').MaterialDao
    token, row = await repo.claim(db, 101)
    await env.materials.MaterialService.retry_parse(db, 7, 101)
    assert await material_repo.list_material_ids_for_dispatch(db) == []
    assert await material_repo.claim_material_parse(db, 101) is None
    assert not await repo.finish(
        db, 101, token=token, status='completed', category_id=801, expected_version=row.version
    )
    claimed = await material_repo.claim_material_parse(db, 101)
    assert claimed is not None
    assert await material_repo.finish_material_parse(
        db,
        101,
        parse_token=claimed._parse_token,
        status='ready',
        extracted_text='最新提取正文',
    )
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.extracted_text == '最新提取正文' and current.classification_status == 'not_configured'


@pytest.mark.asyncio
async def test_parse_completion_preserves_a_still_running_classification_slot(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    material_repo = importlib.import_module('app.library.repositories.material_repository')
    token, _ = await repo.claim(db, 101)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    current.status = 'parsing'  # Legacy/hot-upgrade overlap, not newly dispatched by this worker.
    await db.commit()
    parse_token = await material_repo._sqlite_parse_token(db)
    assert await material_repo.MaterialDao.finish_material_parse(
        db,
        101,
        parse_token=parse_token,
        status='ready',
        extracted_text='重新提取正文',
    )
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.classification_status == 'running' and current.classification_token == token
    assert not await repo.finish(db, 101, token=token, status='completed', category_id=801)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.category_id is None and current.classification_status == 'not_configured'


@pytest.mark.asyncio
async def test_old_classification_settling_during_parse_queues_a_fresh_parse(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    material_repo = importlib.import_module('app.library.repositories.material_repository').MaterialDao
    token, _ = await repo.claim(db, 101)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    current.status = 'parsing'
    await db.commit()
    assert not await repo.finish(db, 101, token=token, status='completed', category_id=801)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.status == 'queued' and current.classification_status == 'not_configured'
    assert await material_repo.claim_material_parse(db, 101)


@pytest.mark.asyncio
async def test_running_classification_cannot_be_deleted_or_its_slot_removed(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    token, _ = await repo.claim(db, 101)
    with pytest.raises(env.exc) as waiting:
        await env.materials.MaterialService.delete_material(db, 7, 101)
    assert '等待本次执行结束' in waiting.value.message
    assert await repo.is_current(db, 101, token=token, version=1)


@pytest.mark.asyncio
async def test_edited_interrupted_call_never_automatically_replays_paid_request(env, db):
    await configured(env, db)
    module = importlib.import_module('app.library.repositories.classification_repository')
    token, row = await module.MaterialClassificationDao.claim(db, 101)
    await env.materials.MaterialService.edit(db, 7, 101, expected_version=1, edited_text='最新正文')
    assert not await module.MaterialClassificationDao.finish(
        db,
        101,
        token=token,
        status='failed',
        error=module.INTERRUPTED_MESSAGE,
        expected_version=row.version,
    )
    assert await module.MaterialClassificationDao.ready(db) == []
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.classification_status == 'failed' and current.edited_text == '最新正文'


@pytest.mark.asyncio
async def test_reparse_finishing_after_old_call_interrupted_does_not_requeue_paid_classification(env, db):
    await configured(env, db)
    module = importlib.import_module('app.library.repositories.classification_repository')
    material_repo = importlib.import_module('app.library.repositories.material_repository').MaterialDao
    token, row = await module.MaterialClassificationDao.claim(db, 101)
    await env.materials.MaterialService.retry_parse(db, 7, 101)
    assert not await module.MaterialClassificationDao.finish(
        db,
        101,
        token=token,
        status='failed',
        error=module.INTERRUPTED_MESSAGE,
        expected_version=row.version,
    )
    parsed = await material_repo.claim_material_parse(db, 101)
    assert parsed and await material_repo.finish_material_parse(
        db,
        101,
        parse_token=parsed._parse_token,
        status='ready',
        extracted_text='最新提取正文',
    )
    assert await module.MaterialClassificationDao.ready(db) == []
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.status == 'ready' and current.classification_status == 'failed'
    assert current.classification_error == module.INTERRUPTED_MESSAGE
    result = await env.materials.MaterialService.retry_classification(db, 7, 101)
    assert result['classificationStatus'] == 'queued'


@pytest.mark.asyncio
async def test_provider_guard_runs_after_context_preparation_and_sends_nothing_if_stale(env, db):
    row = await configured(env, db)
    service = importlib.import_module('app.library.services.classification')
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(kwargs)
        raise AssertionError('Superseded text was sent to provider')

    async def no_longer_current():
        return False

    with pytest.raises(service.ClassificationSuperseded):
        await service.MaterialClassificationService.classify(
            db,
            title=row.name,
            content=row.extracted_text,
            request_id='stale-before-call',
            gateway=forbidden,
            before_call=no_longer_current,
        )
    assert calls == []


@pytest.mark.asyncio
async def test_edit_during_scan_is_detected_before_any_provider_call(env, db, tmp_path, monkeypatch):
    await configured(env, db)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    scheduler = importlib.import_module('app.library.tasks.material_parse_scheduler')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', lambda: AsyncMemory(Session(db.s.bind, expire_on_commit=False)))

    async def scan_after_edit(*_args):
        await env.materials.MaterialService.edit(db, 7, 101, expected_version=1, edited_text='扫描期间更新的正文')
        return SimpleNamespace(status='clean')

    async def forbidden(*args, **kwargs):
        raise AssertionError('Old text sent to model after scanner finished')

    monkeypatch.setattr(scheduler.asyncio, 'to_thread', scan_after_edit)
    monkeypatch.setattr(scheduler.MaterialClassificationService, 'classify', forbidden)
    await scheduler.process_material_classification(101)
    db.s.expire_all()
    current = await db.get(env.material.PipelineMaterial, 101)
    assert current.classification_status == 'not_configured' and current.edited_text == '扫描期间更新的正文'
    assert current.category_id is None and current.classification_token is None


@pytest.mark.asyncio
async def test_legacy_queue_without_consent_is_discarded_before_any_model_call(env, db, monkeypatch):
    row = await configured(env, db)
    row.classification_token = None
    await db.commit()
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    assert await repo.claim(db, 101) is None
    assert await repo.ready(db) == []
    db.s.expire_all()
    row = await db.get(env.material.PipelineMaterial, 101)
    assert row.classification_status == 'not_configured' and row.classification_token is None


@pytest.mark.asyncio
async def test_edit_revokes_queued_consent_and_owner_must_submit_again(env, db):
    await configured(env, db)
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    await env.materials.MaterialService.edit(db, 7, 101, expected_version=1, edited_text='新的私有正文')
    assert await repo.ready(db) == [] and await repo.claim(db, 101) is None
    await env.materials.MaterialService.retry_classification(db, 7, 101)
    claim = await repo.claim(db, 101)
    assert claim and claim[1].version == 2 and claim[1].edited_text == '新的私有正文'


@pytest.mark.asyncio
async def test_new_upload_and_parse_never_queue_classification_without_owner_consent(env, db, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    source = tmp_path / 'private.txt'
    source.write_text('私有资料原文，只允许本地解析')
    created = await env.materials.MaterialService.create_material(
        db,
        user_id=7,
        name='private.txt',
        local_path=str(source),
        scanner=lambda *_: SimpleNamespace(status='clean'),
    )
    assert created['classificationStatus'] == 'not_configured'
    dao = importlib.import_module('app.library.repositories.material_repository').MaterialDao
    repo = importlib.import_module('app.library.repositories.classification_repository').MaterialClassificationDao
    parsed = await dao.claim_material_parse(db, created['id'])
    assert await dao.finish_material_parse(
        db,
        created['id'],
        parse_token=parsed._parse_token,
        status='ready',
        extracted_text='私有资料原文，只允许本地解析',
    )
    assert await repo.ready(db) == []
    assert await repo.claim(db, created['id']) is None
