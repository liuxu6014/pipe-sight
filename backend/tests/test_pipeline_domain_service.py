"""直接领域服务回归：提取、安全、私有权限、任务、编辑和历史恢复。"""

import importlib
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import select
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_network
from test_research_simplified_20261025 import payload, queue, raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_network


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-8-sig', 'gb18030', 'utf-16'])
def test_plain_text_material_can_be_extracted_without_external_parser(env, tmp_path, encoding):
    source = tmp_path / '现场记录.txt'
    source.write_bytes('管道应力监测：磁各向异性需要温度补偿。'.encode(encoding))
    assert '磁各向异性需要温度补偿' in env.materials.MaterialFileService.extract_plain_text(str(source), source.name)


def test_docx_material_can_be_extracted_with_standard_library(env, tmp_path):
    source = tmp_path / '应力监测.docx'
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>管道本体应力监测</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>现场应用需要</w:t></w:r><w:r><w:tab/></w:r>'
        '<w:r><w:t>温度补偿</w:t></w:r></w:p></w:body></w:document>'
    )
    with ZipFile(source, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', xml)
    text = env.materials.MaterialFileService.extract_plain_text(str(source), source.name)
    assert text.splitlines() == ['管道本体应力监测', '现场应用需要\t温度补偿']


@pytest.mark.parametrize(
    'limit,value,expected',
    [('max_archive_entries', 1, 'too many archive entries'), ('max_archive_uncompressed_bytes', 4, 'expanded content')],
)
def test_docx_limits_are_checked_before_reading_xml(env, monkeypatch, tmp_path, limit, value, expected):
    source = tmp_path / '受限.docx'
    with ZipFile(source, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', '<document/>')
        archive.writestr('word/styles.xml', '<styles/>')
    monkeypatch.setattr(env.materials.MaterialFileService, limit, value)
    with pytest.raises(ValueError, match=expected):
        env.materials.MaterialFileService._extract_docx_text(source)


def test_searchable_pdf_material_is_ready_after_local_extraction(env, monkeypatch, tmp_path):
    source = tmp_path / '研究报告.pdf'
    source.write_bytes(b'%PDF-1.7')
    monkeypatch.setattr(
        env.materials.MaterialFileService, '_extract_pdf_text', staticmethod(lambda _: '管道完整性与应力监测正文')
    )
    status, message, text, metadata = env.materials.MaterialFileService.parse(
        str(source), source.name, requested_at='offline'
    )
    assert status == 'ready' and 'PDF 已完成文本提取' in message
    assert text == '管道完整性与应力监测正文' and metadata['parser'] == 'pypdf'


def test_pdf_page_limit_is_checked_before_page_extraction(env, monkeypatch, tmp_path):
    source = tmp_path / '页数过多.pdf'
    source.write_bytes(b'%PDF-1.7')
    monkeypatch.setattr(env.materials.MaterialFileService, 'max_pdf_pages', 1)
    monkeypatch.setattr(env.materials, 'PdfReader', lambda _: NS(is_encrypted=False, pages=[object(), object()]))
    with pytest.raises(ValueError, match='page limit'):
        env.materials.MaterialFileService._extract_pdf_text(source)


def test_scanned_or_invalid_pdf_fails_with_actionable_message(env, tmp_path):
    source = tmp_path / '扫描报告.pdf'
    source.write_bytes(b'%PDF-1.7')
    status, message, text, metadata = env.materials.MaterialFileService.parse(
        str(source), source.name, requested_at='offline'
    )
    assert status == 'failed' and '扫描版' in message and text == ''
    assert metadata['parser'] == 'pypdf'


def test_markdown_upload_extension_check_is_case_insensitive(env, monkeypatch):
    upload = importlib.import_module('app.infrastructure.services.file_upload')
    monkeypatch.setattr(upload.UploadConfig, 'DEFAULT_ALLOWED_EXTENSION', ['md', 'txt'], raising=False)
    assert upload.FileUploadSupport.check_file_extension(NS(filename='现场记录.MD'))
    assert not upload.FileUploadSupport.check_file_extension(NS(filename='无后缀'))


@pytest.mark.asyncio
async def test_user_one_never_gets_global_material_access(env, db):
    _, material = seed(env, db)
    assert await env.library_repo.MaterialDao.list_accessible_materials(db, 1) == []
    assert await env.library_repo.MaterialDao.get_owned_material(db, material.id, 1) is None
    assert len(await env.library_repo.MaterialDao.list_accessible_materials(db, 7)) == 1


@pytest.mark.asyncio
async def test_material_detail_exposes_real_text_and_owner_management_flag(env, db):
    _, material = seed(env, db)
    material.edited_text = '用户编辑正文'
    await db.commit()
    result = await env.materials.MaterialService.get_material(db, 7, material.id)
    assert result['canManage'] and result['ownerId'] == 7
    assert result['extractedText'] == '原提取文本' and result['content'] == '用户编辑正文'
    with raises(env, '无权'):
        await env.materials.MaterialService.get_material(db, 8, material.id)


@pytest.mark.asyncio
@pytest.mark.parametrize('scan_status', ['pending', 'quarantined', 'failed'])
async def test_download_rechecks_file_scan_and_rejects_unscanned_material(env, db, tmp_path, monkeypatch, scan_status):
    _, material = seed(env, db)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    source = tmp_path / 'a.txt'
    source.write_text('受控资料', encoding='utf-8')
    monkeypatch.setattr(env.materials.FileScanService, 'scan', lambda *_: NS(status=scan_status))
    with raises(env, '安全扫描'):
        await env.materials.MaterialService.get_download(db, 7, material.id)


@pytest.mark.asyncio
async def test_download_requires_owner_and_returns_original_filename(env, db, tmp_path, monkeypatch):
    _, material = seed(env, db)
    material.name = '用户改名不改变原文件名'
    await db.commit()
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    source = tmp_path / 'a.txt'
    source.write_text('受控资料', encoding='utf-8')
    monkeypatch.setattr(env.materials.FileScanService, 'scan', lambda *_: NS(status='clean'))
    with raises(env, '无权'):
        await env.materials.MaterialService.get_download(db, 8, material.id)
    path, name, mime = await env.materials.MaterialService.get_download(db, 7, material.id)
    assert path == source.resolve() and name == 'a.txt' and mime == 'text/plain'


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['queued', 'parsing', 'failed'])
async def test_unusable_selected_material_is_explicit_error_not_silently_dropped(env, db, monkeypatch, status):
    _, material = seed(env, db)
    material.status = status
    await db.commit()
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    with raises(env, '解析就绪'):
        await queue(env, db)


@pytest.mark.asyncio
async def test_invalid_selection_never_falls_back_to_unselected_materials(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    with raises(env, '无权'):
        await queue(env, db, payload(selected_item_ids=['999999']))
    assert not db.s.scalars(select(env.models.PipelineResearchJob)).all()
    with raises(env, '1 至 50'):
        await queue(env, db, payload(selected_item_ids=[]))


@pytest.mark.asyncio
async def test_task_is_persisted_with_report_and_frozen_template_before_processing(env, db, monkeypatch):
    template, _ = seed(env, db)
    template.sections = [{'id': 1, 'title': '真实模板章节'}]
    await db.commit()
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    assert result['status'] == 'queued' and result['progress'] == 0 and result['reportId']
    assert job.config_snapshot['template']['sections'] == [{'id': 1, 'title': '真实模板章节'}]
    assert job.materials[0]['content'] == '原提取文本'
    template.sections = [{'id': 2, 'title': '后续修改'}]
    await db.commit()
    assert job.config_snapshot['template']['sections'][0]['title'] == '真实模板章节'
    repeated = await queue(env, db)
    assert repeated['reused'] and repeated['jobId'] == str(job.id)


@pytest.mark.asyncio
@pytest.mark.parametrize('status,label', [('cancelled', '已取消'), ('failed', '生成失败')])
async def test_job_status_labels_cover_terminal_states(env, db, monkeypatch, status, label):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    job.status = status
    assert env.app.ResearchApplicationService.job_dict(job)['statusLabel'] == label


@pytest.mark.parametrize('submitted', [
    [{'id': 1, 'title': '实际提交章节', 'words': 1000}, {'id': 2, 'title': '后续章节', 'words': 2000}],
    [],
    None,
])
def test_job_progress_outline_matches_submitted_snapshot_not_template_defaults(env, submitted):
    template = [{'id': 1, 'title': '模板默认章节', 'words': 10600}]
    request = {'outline': submitted} if submitted is not None else {}
    job = env.models.PipelineResearchJob(
        id=501, report_id=502, request_id='outline-display-test', status='queued', progress=0,
        attempts=0, materials=[], config_snapshot={'request': request, 'template': {'sections': template}},
    )
    result = env.app.ResearchApplicationService.job_dict(job)
    expected = template if submitted is None else submitted
    assert result['outline'] == expected
    assert sum(section['words'] for section in result['outline']) == sum(section['words'] for section in expected)
    assert result['config'] == request


@pytest.mark.parametrize('status', ['queued', 'running', 'completed', 'failed', 'cancelled'])
def test_job_execution_display_matches_real_terminal_state(env, status):
    from datetime import datetime

    job = env.models.PipelineResearchJob(
        id=601, report_id=602, request_id='execution-display', status=status,
        progress=100 if status == 'completed' else 0, attempts=0 if status == 'queued' else 1,
        materials=[], config_snapshot={'model': {'id': '1'}},
        result_content='## 正文\n生成正文' if status == 'completed' else None,
        created_at=datetime(2026, 10, 25, 10, 0),
        started_at=None if status == 'queued' else datetime(2026, 10, 25, 10, 1),
        finished_at=datetime(2026, 10, 25, 10, 2) if status in {'completed', 'failed', 'cancelled'} else None,
    )
    result = env.app.ResearchApplicationService.job_dict(job)
    assert result['generationMode'] == 'model'
    assert result['logs'] and result['logs'][0]['time'] == '2026-10-25 10:00:00'
    assert result['stage'] == status
    assert result['startedAt'] == ('' if status == 'queued' else '2026-10-25 10:01:00')
    if status in {'completed', 'failed', 'cancelled'}:
        assert not any(row['status'] in {'running', 'waiting'} for row in result['stages'])
        assert result['finishedAt'] == '2026-10-25 10:02:00'
    if status == 'completed':
        assert all(row['status'] == 'completed' for row in result['stages'])
        assert '已保存' in result['logs'][-1]['message']
    else:
        assert not any(row['key'] == 'result' and row['status'] == 'completed' for row in result['stages'])


@pytest.mark.parametrize('name', ['科研需求报告', '科技项目需求填报表', ''])
def test_job_template_name_uses_frozen_template_not_request_id(env, name):
    job = env.models.PipelineResearchJob(
        id=701, report_id=702, request_id='template-name-display', status='queued', progress=0,
        attempts=0, materials=[], config_snapshot={
            'template': {'id': '31', 'name': name},
            'request': {'template_id': '31'},
        },
    )
    result = env.app.ResearchApplicationService.job_dict(job)
    assert result['templateName'] == name
    assert result['config']['template_id'] == '31'


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['queued', 'running'])
async def test_active_job_cannot_be_explicitly_retried(env, db, monkeypatch, status):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    job.status = status
    await db.commit()
    with raises(env, '只能重试失败'):
        await env.app.ResearchApplicationService.queue_retry(db, user_id=7, job_id=job.id)


@pytest.mark.asyncio
async def test_running_task_cancel_fences_executor_and_keeps_report(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.claim_research_job(db, result['jobId'], 7)
    token = job.execution_token
    result = await env.app.ResearchApplicationService.cancel_job(db, 7, job.id)
    assert result['status'] == 'cancelled'
    assert not await env.repo.ResearchDao.lock_running_research_job(db, job.id, 7, token)
    assert await env.repo.ResearchDao.get_report(db, job.report_id, 7)


@pytest.mark.asyncio
async def test_report_edit_rejects_stale_version_and_revision_without_overwriting(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    service = env.app.ResearchApplicationService
    with raises(env, '版本'):
        await service.update_report(
            db,
            user_id=7,
            owner_name='用户',
            report_id=result['reportId'],
            payload=NS(expected_version=2, expected_revision=None, title='覆盖标题', content='不能保存'),
        )
    with raises(env, '修订'):
        await service.update_report(
            db,
            user_id=7,
            owner_name='用户',
            report_id=result['reportId'],
            payload=NS(
                expected_version=1, expected_revision='2026-01-01T00:00:00', title='覆盖标题', content='不能保存'
            ),
        )
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    assert report.title == '测试报告' and report.content == '' and report.version == 1


@pytest.mark.asyncio
async def test_only_owner_can_retry_parse_and_retry_preserves_edited_text(env, db):
    _, material = seed(env, db)
    material.status = 'failed'
    material.edited_text = '保留用户编辑'
    await db.commit()
    with raises(env, '无权'):
        await env.materials.MaterialService.retry_parse(db, 8, material.id)
    result = await env.materials.MaterialService.retry_parse(db, 7, material.id)
    assert result['parseStatus'] == 'queued' and result['editedText'] == '保留用户编辑'
    assert result['extractedText'] == '原提取文本'


@pytest.mark.asyncio
async def test_owner_delete_cascades_basket_and_removes_only_owned_file(env, db, tmp_path, monkeypatch):
    _, material = seed(env, db)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    source = tmp_path / 'a.txt'
    source.write_text('待删除正文', encoding='utf-8')
    await env.app.ResearchWorkspaceService.upsert_item(
        db, 7, NS(item_type='file', item_id=material.id, action='basket')
    )
    with raises(env, '无权'):
        await env.materials.MaterialService.delete_material(db, 8, material.id)
    assert source.exists()
    result = await env.materials.MaterialService.delete_material(db, 7, material.id)
    assert result['fileDeleted'] and result['historicalSnapshotsRetained']
    assert not source.exists() and not await env.repo.ResearchDao.list_workspace_items(db, 7)
    assert await env.library_repo.MaterialDao.get_owned_material(db, material.id, 7) is None


@pytest.mark.asyncio
async def test_report_history_requires_owner_and_restores_as_new_version(env, db, monkeypatch):
    seed(env, db)
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    service = env.app.ResearchApplicationService
    for version, content in [(1, '第一稿'), (2, '第二稿')]:
        await service.update_report(
            db,
            user_id=7,
            owner_name='用户',
            report_id=result['reportId'],
            payload=NS(expected_version=version, expected_revision=None, title=None, content=content),
        )
    with raises(env, '无权'):
        await service.get_report_version(db, 8, result['reportId'], 2)
    history = await service.get_report_version(db, 7, result['reportId'], 2)
    assert history['content'] == '第一稿'
    restored = await service.restore_report_version(
        db, user_id=7, owner_name='用户', report_id=result['reportId'], version_no=2
    )
    assert restored['versionNo'] == 4 and restored['content'] == '第一稿'
    old_current = await service.get_report_version(db, 7, result['reportId'], 3)
    assert old_current['content'] == '第二稿'


@pytest.mark.asyncio
async def test_generated_images_are_owned_assets_not_report_metadata(env, db, monkeypatch):
    template, _ = seed(env, db, image=True)
    template.image_config = {'enabled': True, 'count': 1, 'prompt': '真实管道示意'}
    await db.commit()
    monkeypatch.setattr(env.repo.ResearchDao, 'load_content', AsyncMock(return_value=None))
    result = await queue(env, db)
    job = await env.repo.ResearchDao.get_research_job(db, result['jobId'], 7)
    report = await env.repo.ResearchDao.get_report(db, result['reportId'], 7)
    await env.app.ResearchReportExportService.queue_images(db, job, report)
    await db.commit()
    images = await env.app.ResearchReportService.get_diagram(db, 7, report.id)
    assert len(images['images']) == 1 and images['images'][0]['status'] == 'queued'
    with raises(env, '无权'):
        await env.app.ResearchReportService.get_diagram(db, 8, report.id)
    assert not hasattr(report, 'metadata_json')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'options,message', [({'language': 'bilingual'}, '简体中文'), ({'publicSupplement': True}, '公开补充')]
)
async def test_unsupported_generation_options_fail_without_model_call(env, options, message):
    with raises(env, message):
        await env.app.ResearchApplicationService.queue_job(
            object(), user_id=7, owner_name='用户', payload=payload(options=options)
        )


def test_report_markdown_sections_preserve_actual_content_without_generation(env):
    module = importlib.import_module('app.research.services.report_content')
    assert module.sections_from_markdown('直接正文') == [{'id': 1, 'title': '正文', 'content': '直接正文'}]
    assert module.sections_from_markdown('# 报告\n\n## 背景\n\n现场证据\n\n## 结论\n\n用户结论') == [
        {'id': 1, 'title': '背景', 'content': '现场证据'},
        {'id': 2, 'title': '结论', 'content': '用户结论'},
    ]


@pytest.mark.asyncio
async def test_sources_are_read_directly_from_persistent_source_service(env, monkeypatch):
    module = importlib.import_module('app.intelligence.services.sources')
    source = NS(**{column.name: None for column in module.Source.__table__.columns})
    source.id, source.name, source.type = 601, '科技资讯源', 'website'
    source.adapter, source.config, source.is_enabled = 'registered', {}, True
    database = NS(execute=AsyncMock(return_value=NS(scalars=lambda: NS(all=lambda: [source]))))
    result = await module.IntelligenceSourceService.list_sources(database)
    assert result['total'] == 1 and result['rows'][0]['id'] == '601'
    assert result['rows'][0]['type'] == 'website'


@pytest.mark.asyncio
async def test_manual_collection_queues_using_collection_repository_not_main_dao(env, monkeypatch):
    module = importlib.import_module('app.intelligence.services.sources')
    source = NS(id=601, adapter='registered', url='https://offline.invalid', type='website', config={}, model_id=None)
    run = NS(**{column.name: None for column in module.Run.__table__.columns})
    run.id, run.source_id, run.status, run.trigger_type = 701, source.id, 'queued', 'manual'
    run.request_id = 'manual:offline'
    get = AsyncMock(return_value=source)
    active = AsyncMock(return_value=None)
    enqueue = AsyncMock(return_value=run)
    monkeypatch.setattr(module.CollectionRepository, 'source', get)
    monkeypatch.setattr(module.CollectionRepository, 'active', active)
    monkeypatch.setattr(module.CollectionRepository, 'enqueue', enqueue)
    database = NS(rollback=AsyncMock())
    validate = []
    result = await module.IntelligenceSourceService.queue_collection_run(
        database, source.id, registry=NS(validate=lambda config: validate.append(config))
    )
    assert result['status'] == 'queued' and result['sourceId'] == str(source.id)
    get.assert_awaited_once_with(database, source.id, lock=True)
    active.assert_awaited_once_with(database, source.id)
    enqueue.assert_awaited_once()
    assert validate[0]['adapter'] == 'registered'
