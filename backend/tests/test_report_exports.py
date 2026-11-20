"""规范资源表导出：冻结正文、本人权限、稳定文件键与实际字节完整性。"""

import hashlib
import importlib
from types import SimpleNamespace as NS
from typing import NoReturn

import pytest
from sqlalchemy.orm import Session
from test_research_simplified_20261025 import AsyncMemory, raises, seed
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_network

env = refactor_env
db = refactor_db
no_external_network = refactor_network


async def finished_export_context(env, db, tmp_path, monkeypatch):
    module, report, result = await report_and_export(env, db)
    export_context(module, env, db, tmp_path, monkeypatch)
    storage = module.ReportExportStorage
    key = storage.build_key(result['id'], 'pdf', 2026, 11, 20)
    storage.write(key, b'synthetic report')
    asset = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    asset.status, asset.storage_key = 'completed', key
    await db.commit()
    scheduler = importlib.import_module('app.research.tasks.research_job_scheduler')
    monkeypatch.setattr(scheduler, 'AsyncSessionLocal', module.AsyncSessionLocal)
    return module, report, storage, key, scheduler


@pytest.mark.asyncio
async def test_report_delete_retries_failed_resource_removal(env, db, tmp_path, monkeypatch):
    module, report, storage, key, scheduler = await finished_export_context(env, db, tmp_path, monkeypatch)

    def unavailable(_key):
        raise OSError('simulated storage failure')

    with monkeypatch.context() as temporary:
        temporary.setattr(storage, 'finish_cleanup', unavailable)
        await module.ResearchReportService.delete_report(db, user_id=7, report_id=report.id)
    assert storage.read(key) == b'synthetic report'
    assert storage._resolve(storage.cleanup_marker(key)).is_file()
    await scheduler.clean_deleted_report_files()
    assert not storage._resolve(key).exists()
    assert not list(storage.cleanup_directory().iterdir())


@pytest.mark.asyncio
async def test_report_delete_cleans_export_and_image_files(env, db, tmp_path, monkeypatch):
    module, report, storage, key, _scheduler = await finished_export_context(env, db, tmp_path, monkeypatch)
    image_key = storage.build_key('image', 'png', 2026, 11, 20)
    storage.write(image_key, b'synthetic image')
    db.add(
        env.ai.AiModels(
            id=2,
            name='图片',
            provider='openai-compatible',
            code='image',
            base_url='https://offline.invalid/v1',
            credential_ref='env:OFFLINE_MODEL_KEY',
            capabilities=['image_generate'],
            parameters={},
            is_enabled=True,
        )
    )
    await db.flush()
    db.add(
        env.models.PipelineReportAsset(
            report_id=report.id,
            type='image',
            mime_type='image/png',
            model_id=2,
            prompt='synthetic image',
            storage_key=image_key,
            status='completed',
        )
    )
    await db.commit()
    await module.ResearchReportService.delete_report(db, user_id=7, report_id=report.id)
    assert not storage._resolve(key).exists()
    assert not storage._resolve(image_key).exists()
    assert not list(storage.cleanup_directory().iterdir())


@pytest.mark.asyncio
async def test_rolled_back_report_deletion_cannot_remove_live_file(env, db, tmp_path, monkeypatch):
    module, report, storage, key, scheduler = await finished_export_context(env, db, tmp_path, monkeypatch)

    async def fail_commit():
        raise RuntimeError('simulated transaction failure')

    with monkeypatch.context() as temporary:
        temporary.setattr(db, 'commit', fail_commit)
        with pytest.raises(RuntimeError, match='transaction failure'):
            await module.ResearchReportService.delete_report(db, user_id=7, report_id=report.id)
    db.s.rollback()
    assert storage._resolve(storage.cleanup_marker(key)).is_file()
    await scheduler.clean_deleted_report_files()
    assert storage.read(key) == b'synthetic report'
    assert not list(storage.cleanup_directory().iterdir())


def test_cleanup_key_cannot_escape_controlled_export_directory(tmp_path, monkeypatch):
    from app.research.services.export_storage import ReportExportStorage
    from config.env import UploadConfig

    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    outside = tmp_path.parent / f'{tmp_path.name}-unrelated.txt'
    outside.write_text('keep')
    unrelated_upload = tmp_path / 'private-original.txt'
    unrelated_upload.write_text('keep original')
    for key in (
        '../' + outside.name,
        'report_exports/../../' + outside.name,
        str(outside),
        'report_exports/../private-original.txt',
    ):
        with pytest.raises(ValueError, match='存储键无效'):
            ReportExportStorage.schedule_cleanup(key)
    assert outside.read_text() == 'keep'
    assert unrelated_upload.read_text() == 'keep original'


async def report_and_export(env, db, *, with_history=False):
    template, material = seed(env, db, model=False)
    report = env.models.PipelineReport(
        id=301,
        user_id=7,
        title='年度报告',
        type='research',
        template_id=201,
        content='# 结论\n\n导出提交时的真实正文',
        version=4,
    )
    db.add(report)
    await db.flush()
    if with_history:
        db.add(
            env.models.PipelineReportVersion(
                report_id=report.id,
                version=4,
                title=report.title,
                content=report.content,
                source='manual',
                operator_id=7,
                operator_name='历史编辑者',
                sections=[{'title': '结论', 'content': '导出提交时的真实正文'}],
                citations=[
                    {
                        'id': 1,
                        'type': 'file',
                        'sourceId': str(material.id),
                        'title': material.name,
                        'source': {'filename': material.filename},
                    }
                ],
                quality_issues=[{'message': '人工待核对'}],
                model_snapshot={
                    'template': {'id': str(template.id), 'name': template.name},
                    'request': {'period': ['2026-01-01', '2026-03-31']},
                },
            )
        )
    await db.commit()
    module = importlib.import_module('app.research.services.exports')
    result = await module.ResearchReportExportService.create(db, user_id=7, report_id=report.id, file_format='pdf')
    return module, report, result


def export_context(module, env, db, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))

    def factory():
        return AsyncMemory(Session(db.s.bind, expire_on_commit=False))

    monkeypatch.setattr(module, 'AsyncSessionLocal', factory)


@pytest.mark.asyncio
async def test_create_export_persists_exact_snapshot_without_deleted_entity_columns(env, db) -> None:
    _module, report, result = await report_and_export(env, db)
    record = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    assert result['status'] == 'queued' and result['reportVersionNo'] == 4
    assert record.type == 'export' and record.task_id is None and record.mime_type == 'application/pdf'
    assert record.storage_key is None
    assert record.config_snapshot == {
        'version': 4,
        'revision': importlib.import_module('app.research.services.report_revision').report_revision(report),
        'allowDraft': False,
        'report': {
            'title': '年度报告',
            'content': '# 结论\n\n导出提交时的真实正文',
            'version_no': 4,
            'report_type': 'research',
            'owner_name': '',
            'sections': [],
            'citations': [],
            'metadata': {},
        },
    }
    report.content = '提交后的编辑内容'
    report.version += 1
    await db.commit()
    assert record.config_snapshot['report']['content'] == '# 结论\n\n导出提交时的真实正文'
    assert not {'file_hash', 'file_size', 'format', 'user_id', 'snapshot'} & set(record.__table__.c.keys())


@pytest.mark.asyncio
async def test_create_export_preserves_exact_actual_history_metadata_without_inventing_model_or_owner(env, db) -> None:
    _, report, result = await report_and_export(env, db, with_history=True)
    record = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    assert record.config_snapshot == {
        'version': 4,
        'revision': importlib.import_module('app.research.services.report_revision').report_revision(report),
        'allowDraft': False,
        'report': {
            'title': '年度报告',
            'content': '# 结论\n\n导出提交时的真实正文',
            'version_no': 4,
            'report_type': 'research',
            'owner_name': '',
            'sections': [{'title': '结论', 'content': '导出提交时的真实正文'}],
            'citations': [
                {'id': 1, 'type': 'file', 'sourceId': '101', 'title': '资料', 'source': {'filename': 'a.txt'}}
            ],
            'metadata': {
                'modelSnapshot': {
                    'template': {'id': '201', 'name': '模板'},
                    'request': {'period': ['2026-01-01', '2026-03-31']},
                },
                'source': 'manual',
                'operator': '历史编辑者',
                'qualityIssues': [{'message': '人工待核对'}],
                'templateId': '201',
                'templateVersion': '模板',
                'period': ['2026-01-01', '2026-03-31'],
            },
        },
    }


@pytest.mark.asyncio
async def test_export_reuses_only_matching_pending_snapshot_format_and_draft_mode(env, db) -> None:
    module, report, first = await report_and_export(env, db)
    create = module.ResearchReportExportService.create
    assert (await create(db, user_id=7, report_id=report.id, file_format='pdf'))['id'] == first['id']
    record = await env.repo.ResearchDao.get_asset(db, first['id'], 7)
    record.status = 'running'
    await db.commit()
    assert (await create(db, user_id=7, report_id=report.id, file_format='pdf'))['id'] == first['id']
    word = await create(db, user_id=7, report_id=report.id, file_format='docx')
    assert word['id'] != first['id']
    draft = await create(db, user_id=7, report_id=report.id, file_format='pdf', allow_draft=True)
    assert draft['id'] not in {word['id'], first['id']}
    # A same-number autosave can still change content/revision and must get new bytes.
    report.content = '同版本号的新正文'
    await db.commit()
    changed = await create(db, user_id=7, report_id=report.id, file_format='pdf')
    assert changed['id'] not in {word['id'], first['id'], draft['id']}
    changed_record = await env.repo.ResearchDao.get_asset(db, changed['id'], 7)
    assert changed_record.config_snapshot['report']['content'] == '同版本号的新正文'
    report.version += 1
    await db.commit()
    next_version = await create(db, user_id=7, report_id=report.id, file_format='pdf')
    assert next_version['id'] != changed['id']
    with raises(env, '无权'):
        await create(db, user_id=8, report_id=report.id, file_format='pdf')
    other = env.models.PipelineReport(
        id=302,
        user_id=8,
        title=report.title,
        type=report.type,
        content=report.content,
        version=report.version,
    )
    db.add(other)
    await db.commit()
    other_export = await create(db, user_id=8, report_id=other.id, file_format='pdf')
    assert other_export['id'] != next_version['id'] and other_export['reportId'] == '302'


@pytest.mark.asyncio
async def test_completed_and_failed_exports_are_not_reused_as_new_pending_requests(env, db) -> None:
    module, report, first = await report_and_export(env, db)
    record = await env.repo.ResearchDao.get_asset(db, first['id'], 7)
    record.status = 'failed'
    await db.commit()
    next_one = await module.ResearchReportExportService.create(db, user_id=7, report_id=report.id, file_format='pdf')
    assert next_one['id'] != first['id']
    record = await env.repo.ResearchDao.get_asset(db, next_one['id'], 7)
    record.status, record.storage_key = 'completed', 'synthetic-export.pdf'
    await db.commit()
    final = await module.ResearchReportExportService.create(db, user_id=7, report_id=report.id, file_format='pdf')
    assert final['id'] not in {first['id'], next_one['id']}


def test_export_render_metadata_reads_explicit_renderer_dto(env) -> None:
    exporter = importlib.import_module('app.research.services.exporters')
    snapshot = NS(
        report_type='research-demand',
        version_no=4,
        owner_name='测试用户',
        metadata={'templateVersion': 'V2.0', 'period': ['2026-01-01', '2026-03-31']},
    )
    assert exporter._metadata_line(snapshot) == ('类型：科研需求报告　负责人：测试用户　周期：2026-01-01 至 2026-03-31')


@pytest.mark.asyncio
async def test_process_export_writes_real_pdf_and_download_preserves_exact_bytes(
    env, db, tmp_path, monkeypatch
) -> None:
    module, report, result = await report_and_export(env, db)
    export_context(module, env, db, tmp_path, monkeypatch)
    report.content = '导出排队之后编辑的正文'
    await db.commit()
    captured = []
    original = module.build_file

    def render(snapshot, extension, **kwargs):
        captured.append(snapshot.content)
        return original(snapshot, extension, **kwargs)

    monkeypatch.setattr(module, 'build_file', render)
    await module.ResearchReportExportService.process(result['id'])
    db.s.expire_all()
    record = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    assert record.status == 'completed' and record.storage_key and record.error is None
    persisted = module.ReportExportStorage.read(record.storage_key)
    assert persisted.startswith(b'%PDF-')
    name, mime, downloaded = await module.ResearchReportExportService.download(db, user_id=7, export_id=record.id)
    assert mime == 'application/pdf' and name == f'{record.id}.pdf'
    assert hashlib.sha256(downloaded).digest() == hashlib.sha256(persisted).digest()
    assert downloaded == persisted and captured == ['# 结论\n\n导出提交时的真实正文']


@pytest.mark.asyncio
async def test_export_and_download_require_report_owner_before_touching_file(env, db, monkeypatch) -> None:
    module, report, result = await report_and_export(env, db)

    def forbidden(*args, **kwargs) -> NoReturn:
        raise AssertionError('unauthorized user reached file storage')

    monkeypatch.setattr(module.ReportExportStorage, 'read', forbidden)
    with raises(env, '无权'):
        await module.ResearchReportExportService.create(db, user_id=8, report_id=report.id, file_format='pdf')
    with raises(env, '无权'):
        await module.ResearchReportExportService.download(db, user_id=8, export_id=result['id'])


@pytest.mark.asyncio
async def test_queued_export_is_not_downloadable(env, db) -> None:
    module, _, result = await report_and_export(env, db)
    with raises(env, '尚未完成'):
        await module.ResearchReportExportService.download(db, user_id=7, export_id=result['id'])


@pytest.mark.asyncio
async def test_recovery_reuses_existing_file_without_rendering_again(env, db, tmp_path, monkeypatch) -> None:
    module, _, result = await report_and_export(env, db)
    export_context(module, env, db, tmp_path, monkeypatch)
    record = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    key = module.ReportExportStorage.build_key(
        record.id, 'pdf', record.created_at.year, record.created_at.month, record.created_at.day
    )
    module.ReportExportStorage.write(key, b'%PDF-previously-written')

    def forbidden(*args, **kwargs) -> NoReturn:
        raise AssertionError('persisted file was regenerated')

    monkeypatch.setattr(module, 'build_file', forbidden)
    await module.ResearchReportExportService.process(record.id)
    db.s.expire_all()
    current = await env.repo.ResearchDao.get_asset(db, record.id, 7)
    assert current.status == 'completed'
    assert module.ReportExportStorage.read(current.storage_key) == b'%PDF-previously-written'


@pytest.mark.asyncio
async def test_export_failure_is_safe_and_can_be_explicitly_retried(env, db, tmp_path, monkeypatch) -> None:
    module, _, result = await report_and_export(env, db)
    export_context(module, env, db, tmp_path, monkeypatch)

    def failed(*args, **kwargs) -> NoReturn:
        raise RuntimeError('private filesystem path and secret must not escape')

    monkeypatch.setattr(module, 'build_file', failed)
    await module.ResearchReportExportService.process(result['id'])
    db.s.expire_all()
    record = await env.repo.ResearchDao.get_asset(db, result['id'], 7)
    assert record.status == 'failed' and record.storage_key is None
    assert 'private filesystem' not in record.error
    assert (await module.ResearchReportExportService.retry(db, 7, record.id))['status'] == 'queued'


def test_export_storage_rejects_path_traversal(env, tmp_path, monkeypatch) -> None:
    module = importlib.import_module('app.research.services.export_storage')
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    for key in ('../outside.pdf', 'report_exports/../../outside.pdf', '/tmp/outside.pdf'):
        with pytest.raises(ValueError):
            module.ReportExportStorage.read(key)


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['missing', 'disabled', 'wrong_capability', 'unsupported_provider', 'enabled'])
async def test_image_retry_validates_model_before_mutating_failed_asset(env, db, monkeypatch, state) -> None:
    module, report, _ = await report_and_export(env, db)
    model = env.ai.AiModels(
        id=2,
        name='图片',
        provider='compatible',
        code='image',
        base_url='https://offline.invalid/v1',
        credential_ref='env:OFFLINE_MODEL_KEY',
        capabilities=['image_generate'],
        parameters={},
        is_enabled=True,
    )
    db.add(model)
    await db.flush()
    record = env.models.PipelineReportAsset(
        id=401,
        report_id=report.id,
        type='image',
        model_id=2,
        prompt='真实图片提示词',
        mime_type='image/png',
        status='failed',
        error='原图片失败原因',
        config_snapshot={'model': {'id': '2'}},
    )
    db.add(record)
    if state == 'missing':

        async def missing(*args) -> None:
            return None

        monkeypatch.setattr(env.repo.ResearchDao, 'get_model', missing)
    elif state == 'disabled':
        model.is_enabled = False
    elif state == 'wrong_capability':
        model.capabilities = ['image_input']
    elif state == 'unsupported_provider':
        model.provider = 'anthropic'
    await db.commit()
    if state == 'enabled':
        assert (await module.ResearchReportExportService.retry(db, 7, record.id))['status'] == 'queued'
        assert record.error is None
    else:
        with raises(env, '协议' if state == 'unsupported_provider' else 'image_generate'):
            await module.ResearchReportExportService.retry(db, 7, record.id)
        await db.commit()
        db.s.expire_all()
        current = await env.repo.ResearchDao.get_asset(db, record.id, 7)
        assert current.status == 'failed' and current.error == '原图片失败原因'
        assert current.storage_key is None
