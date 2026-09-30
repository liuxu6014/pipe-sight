from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from exceptions.exception import ServiceException
from module_pipeline.dao.pipeline_dao import PipelineDao
from module_pipeline.entity.vo.pipeline_vo import PipelineDiagramUpdateModel, PipelineResearchJobCreateModel
from module_pipeline.service.pipeline_domain_service import PipelineDomainService
from utils.upload_util import UploadUtil


def _material(**overrides):
    values = {
        'file_id': 'doc-1',
        'name': '应力监测资料.md',
        'category': '内部文献',
        'file_name': '应力监测资料.md',
        'file_path': '/profile/upload/2026/08/09/应力监测资料.md',
        'file_url': 'http://localhost/profile/upload/2026/08/09/应力监测资料.md',
        'file_size': 128,
        'permission_scope': 'private',
        'parse_status': 'indexed',
        'parse_message': '文本已完成基础提取，可用于关键词检索。',
        'summary': '磁各向异性信号需要温度补偿。',
        'extracted_text': '磁各向异性信号需要温度补偿。',
        'tags': ['应力监测'],
        'metadata_json': {'parser': 'plain-text', 'parseAttempts': 1},
        'owner_id': 1,
        'owner_name': '测试用户',
        'version_no': 1,
        'create_time': None,
        'update_time': None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_plain_text_material_can_be_extracted_without_external_parser():
    source = Path(__file__).with_name('.pipeline-notes-test.md')
    try:
        source.write_text('# 管道应力监测\n磁各向异性信号需要温度补偿。', encoding='utf-8')

        text = PipelineDomainService.extract_plain_text(str(source), source.name)

        assert '磁各向异性' in text
    finally:
        source.unlink(missing_ok=True)


def test_gb18030_plain_text_material_can_be_extracted(tmp_path):
    source = tmp_path / '现场记录.txt'
    source.write_bytes('管道腐蚀与阴极保护现场记录'.encode('gb18030'))

    text = PipelineDomainService.extract_plain_text(str(source), source.name)

    assert text == '管道腐蚀与阴极保护现场记录'


def test_docx_material_can_be_extracted_with_python_standard_library(tmp_path):
    source = tmp_path / '管道应力监测.docx'
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>管道本体应力监测</w:t></w:r></w:p>
    <w:p><w:r><w:t>现场应用需要</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>温度补偿</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with ZipFile(source, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', document_xml)

    text = PipelineDomainService.extract_plain_text(str(source), source.name)

    assert text.splitlines()[0] == '管道本体应力监测'
    assert '现场应用需要\t温度补偿' in text


def test_searchable_pdf_material_is_extracted_locally(monkeypatch, tmp_path):
    source = tmp_path / '研究报告.pdf'
    source.write_bytes(b'%PDF-1.7')
    monkeypatch.setattr(
        PipelineDomainService,
        '_extract_pdf_text',
        staticmethod(lambda _: '管道完整性管理与应力监测研究内容。'),
    )

    status, message, text, metadata = PipelineDomainService._parse_material_file(str(source), source.name)

    assert status == 'indexed'
    assert 'PDF 已完成文本提取' in message
    assert '应力监测' in text
    assert metadata['parser'] == 'pypdf'


def test_scanned_or_invalid_pdf_fails_with_actionable_message(tmp_path):
    source = tmp_path / '扫描报告.pdf'
    source.write_bytes(b'%PDF-1.7')

    status, message, text, metadata = PipelineDomainService._parse_material_file(str(source), source.name)

    assert status == 'failed'
    assert '扫描版' in message
    assert text == ''
    assert metadata['parser'] == 'pypdf'


def test_research_generator_builds_traceable_sections_and_markdown():
    payload = PipelineResearchJobCreateModel(
        title='管道本体应力监测科研需求报告',
        direction='管道应力监测',
        scenario='科研项目立项',
        requirements='明确现场标定和误差评价方法',
        outline=[{'id': 1, 'title': '技术路线与试验方案', 'words': 1800}],
    )
    evidence = [
        {
            'id': 'paper-001',
            'type': '论文',
            'title': '磁各向异性应力监测综述',
            'summary': '磁信号与轴向应力相关，现场应用需要温度补偿。',
            'source': 'Journal of Pipeline Systems',
            'location': '2026-07-09',
        }
    ]

    sections, citations = PipelineDomainService._build_sections(payload, payload.outline, evidence)
    markdown = PipelineDomainService._build_markdown(payload.title, sections, citations)

    assert sections[0]['citations'] == 1
    assert '[1]' in sections[0]['content']
    assert '## 参考资料' in markdown
    assert '磁各向异性应力监测综述' in markdown


def test_monthly_digest_uses_month_specific_outline_and_digest_content():
    payload = PipelineResearchJobCreateModel(
        title='管网科技情报月报 2026年8月',
        report_type='monthly',
        direction='管网安全、检测技术',
        period=['2026-08-01', '2026-08-31'],
    )
    evidence = [
        {
            'id': 'news-001',
            'type': '科技资讯',
            'title': '多源检测数据融合取得新进展',
            'summary': '现场试验显示融合检测能够提升缺陷识别稳定性。',
            'source': '能源科技观察',
            'location': '2026-08-08',
        }
    ]

    outline = PipelineDomainService._default_outline(payload.report_type)
    sections, citations = PipelineDomainService._build_sections(payload, outline, evidence)

    assert [section['title'] for section in outline] == [
        '月度要闻',
        '重点技术进展',
        '行业趋势与变化',
        '管网应用与实践',
        '风险与机会研判',
        '下月关注',
    ]
    assert len(sections) == 6
    assert citations[0]['sourceId'] == 'news-001'
    assert '汇总本周期可信信息' in sections[0]['content']


def test_scoped_knowledge_search_uses_domain_tokens():
    tokens = PipelineDomainService._query_tokens('磁各向异性应力监测如何温度补偿？')

    assert '磁各向异性应力监测如何温度补偿' in tokens
    assert '温度' in tokens


def test_pipeline_upload_accepts_markdown_case_insensitively():
    assert UploadUtil.check_file_extension(SimpleNamespace(filename='现场记录.MD')) is True
    assert UploadUtil.check_file_extension(SimpleNamespace(filename='现场记录')) is False


def test_job_status_labels_cover_terminal_states():
    base = {
        'task_id': 'job-1',
        'title': '测试任务',
        'report_type': 'research-demand',
        'current_stage': 'completed',
        'progress': 100,
        'owner_name': '测试用户',
        'report_id': 'report-1',
        'selected_items': [],
        'outline': [],
        'stages': [],
        'logs': [],
        'config': {},
        'error_message': None,
        'create_time': None,
        'update_time': None,
    }

    assert PipelineDomainService._job_dict(SimpleNamespace(**base, status='cancelled'))['statusLabel'] == '已取消'
    assert PipelineDomainService._job_dict(SimpleNamespace(**base, status='failed'))['statusLabel'] == '生成失败'


@pytest.mark.asyncio
async def test_running_research_job_can_be_cancelled(monkeypatch):
    job = SimpleNamespace(
        task_id='job-running',
        title='测试任务',
        report_type='research-demand',
        status='running',
        current_stage='writing',
        progress=60,
        owner_name='测试用户',
        report_id=None,
        selected_items=[],
        outline=[],
        stages=[{'key': 'writing', 'label': '章节生成', 'status': 'running'}],
        logs=[],
        config={},
        error_message=None,
        create_time=None,
        update_time=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_research_job', AsyncMock(return_value=job))

    result = await PipelineDomainService.cancel_research_job(query_db, 1, job.task_id)

    assert result['status'] == 'cancelled'
    assert result['statusLabel'] == '已取消'
    assert result['stages'][0]['status'] == 'cancelled'
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_material_detail_uses_access_scope_and_exposes_management_flag(monkeypatch):
    material = _material(owner_id=2, permission_scope='private')
    query_db = SimpleNamespace()
    get_accessible = AsyncMock(return_value=material)
    monkeypatch.setattr(PipelineDao, 'get_accessible_material', get_accessible)

    result = await PipelineDomainService.get_material(query_db, 1, material.file_id)

    assert result['id'] == material.file_id
    assert result['extractedText'] == material.extracted_text
    assert result['canManage'] is False
    get_accessible.assert_awaited_once_with(query_db, material.file_id, 1)


@pytest.mark.asyncio
async def test_material_detail_rejects_cross_scope_access(monkeypatch):
    monkeypatch.setattr(PipelineDao, 'get_accessible_material', AsyncMock(return_value=None))

    with pytest.raises(ServiceException) as exc_info:
        await PipelineDomainService.get_material(SimpleNamespace(), 1, 'doc-private')
    assert exc_info.value.message == '资料不存在或无权访问'


@pytest.mark.asyncio
async def test_only_owner_can_retry_material_parse(monkeypatch):
    monkeypatch.setattr(PipelineDao, 'get_owned_material', AsyncMock(return_value=None))

    with pytest.raises(ServiceException) as exc_info:
        await PipelineDomainService.retry_material_parse(SimpleNamespace(), 1, 'doc-department-shared')
    assert exc_info.value.message == '资料不存在或无权重新解析'


@pytest.mark.asyncio
async def test_owner_can_retry_docx_material_parse(monkeypatch, tmp_path):
    source = tmp_path / '应力监测.docx'
    with ZipFile(source, 'w', ZIP_DEFLATED) as archive:
        archive.writestr(
            'word/document.xml',
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>磁各向异性应力监测</w:t></w:r></w:p></w:body></w:document>',
        )
    material = _material(
        name=source.name,
        file_path='/profile/upload/example.docx',
        parse_status='failed',
        parse_message='解析失败',
        extracted_text='',
        metadata_json={'parseAttempts': 1},
    )
    query_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), rollback=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_owned_material', AsyncMock(return_value=material))
    monkeypatch.setattr(PipelineDomainService, '_material_local_path', lambda _: source)

    result = await PipelineDomainService.retry_material_parse(query_db, 1, material.file_id)

    assert result['parseStatus'] == 'indexed'
    assert result['extractedText'] == '磁各向异性应力监测'
    assert result['metadata']['parser'] == 'docx-ooxml'
    assert result['metadata']['parseAttempts'] == 2
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_owner_delete_removes_record_workspace_links_and_local_file(monkeypatch, tmp_path):
    source = tmp_path / '待删除资料.md'
    source.write_text('管道资料', encoding='utf-8')
    material = _material(file_path='/profile/upload/example.md')
    query_db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    delete_material = AsyncMock()
    monkeypatch.setattr(PipelineDao, 'get_owned_material', AsyncMock(return_value=material))
    monkeypatch.setattr(PipelineDao, 'delete_material', delete_material)
    monkeypatch.setattr(PipelineDomainService, '_material_local_path', lambda _: source)

    result = await PipelineDomainService.delete_material(query_db, 1, material.file_id)

    assert result == {'id': material.file_id, 'deleted': True, 'fileDeleted': True}
    assert not source.exists()
    delete_material.assert_awaited_once_with(query_db, material.file_id, 1)
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_report_version_can_be_loaded_and_restored_as_new_version(monkeypatch):
    report = SimpleNamespace(
        report_id='report-1',
        source_task_id='job-1',
        user_id=1,
        owner_name='测试用户',
        title='当前标题',
        report_type='research-demand',
        status='completed',
        version_no=3,
        content='# 当前版本',
        sections=[{'id': 1, 'title': '当前章节', 'content': '当前正文'}],
        citations=[],
        quality_issues=[],
        metadata_json={},
        word_count=4,
        create_time=None,
        update_time=None,
    )
    version = SimpleNamespace(
        report_id='report-1',
        version_no=1,
        title='历史标题',
        content='# 历史版本',
        sections=[{'id': 1, 'title': '历史章节', 'content': '历史正文'}],
        citations=[{'id': 1, 'title': '证据'}],
        source='generated',
        operator_name='生成服务',
        create_time=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_report', AsyncMock(return_value=report))
    monkeypatch.setattr(PipelineDao, 'get_report_version', AsyncMock(return_value=version))
    add_version = AsyncMock()
    monkeypatch.setattr(PipelineDao, 'add_report_version', add_version)

    loaded = await PipelineDomainService.get_report_version(query_db, 1, report.report_id, 1)
    restored = await PipelineDomainService.restore_report_version(
        query_db,
        user_id=1,
        owner_name='测试用户',
        report_id=report.report_id,
        version_no=1,
    )

    assert loaded['content'] == '# 历史版本'
    assert restored['version'] == 'V4.0'
    assert restored['title'] == '历史标题'
    assert restored['citations'][0]['title'] == '证据'
    assert add_version.await_args.args[1].source == 'restored'
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_report_diagram_is_saved_in_owned_report_metadata(monkeypatch):
    report = SimpleNamespace(
        report_id='report-1',
        metadata_json={'templateId': 'tpl-1'},
        update_time=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    monkeypatch.setattr(PipelineDao, 'get_report', AsyncMock(return_value=report))
    payload = PipelineDiagramUpdateModel(
        diagram={
            'diagramType': 'route',
            'direction': 'lr',
            'theme': 'blue',
            'stages': {'input': [], 'analysis': [], 'validation': [], 'output': []},
        }
    )

    saved = await PipelineDomainService.update_report_diagram(
        query_db,
        user_id=1,
        report_id=report.report_id,
        payload=payload,
    )
    loaded = await PipelineDomainService.get_report_diagram(query_db, 1, report.report_id)

    assert saved['diagram']['direction'] == 'lr'
    assert loaded['diagram']['diagramType'] == 'route'
    assert report.metadata_json['templateId'] == 'tpl-1'
    assert report.metadata_json['diagram']['savedAt']
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_research_job_is_persisted_as_queued_before_background_processing(monkeypatch):
    query_db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    add_job = AsyncMock()
    monkeypatch.setattr(PipelineDao, 'add_research_job', add_job)
    payload = PipelineResearchJobCreateModel(
        title='管道完整性科研需求报告',
        selectedItemIds=['paper-001'],
    )

    result = await PipelineDomainService.queue_research_job(
        query_db,
        user_id=1,
        owner_name='测试用户',
        payload=payload,
    )

    assert result['status'] == 'queued'
    assert result['progress'] == 0
    assert result['reportId'] is None
    assert all(stage['status'] == 'waiting' for stage in result['stages'])
    add_job.assert_awaited_once()
    query_db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['queued', 'running'])
async def test_active_research_job_cannot_be_queued_twice(monkeypatch, status):
    job = SimpleNamespace(status=status)
    monkeypatch.setattr(PipelineDao, 'get_research_job', AsyncMock(return_value=job))

    with pytest.raises(ServiceException) as exc_info:
        await PipelineDomainService.queue_research_job_retry(SimpleNamespace(), user_id=1, job_id='job-active')

    assert exc_info.value.message == '任务正在执行，请勿重复提交'


@pytest.mark.asyncio
async def test_research_evidence_never_falls_back_to_unselected_materials(monkeypatch):
    monkeypatch.setattr(PipelineDao, 'list_accessible_materials', AsyncMock(return_value=[_material()]))

    evidence = await PipelineDomainService._resolve_evidence(SimpleNamespace(), 1, [])

    assert evidence == []


@pytest.mark.asyncio
async def test_knowledge_answer_does_not_use_unrelated_or_unparsed_materials(monkeypatch):
    indexed = _material(
        name='管道应力监测资料.md',
        summary='现场应力监测需要进行温度补偿。',
        extracted_text='现场应力监测需要进行温度补偿。',
        parse_status='indexed',
    )
    queued = _material(
        file_id='doc-queued',
        name='海洋生物资料.pdf',
        summary='海洋生物多样性研究。',
        extracted_text='',
        parse_status='queued',
    )
    monkeypatch.setattr(PipelineDao, 'list_accessible_materials', AsyncMock(return_value=[indexed, queued]))

    result = await PipelineDomainService.ask_knowledge(
        SimpleNamespace(),
        user_id=1,
        question='海洋生物多样性有哪些变化？',
    )

    assert result['references'] == []
    assert '没有检索到足以支撑回答的证据' in result['answer']


@pytest.mark.asyncio
async def test_sources_are_read_from_persistent_domain_table(monkeypatch):
    source = SimpleNamespace(
        source_id='source-news',
        name='科技资讯源',
        source_type='news',
        schedule_cron='0 */6 * * *',
        enabled=True,
        status='active',
        last_run_time=None,
        success_count=9,
        failure_count=1,
    )
    monkeypatch.setattr(PipelineDao, 'list_sources', AsyncMock(return_value=[source]))

    result = await PipelineDomainService.list_sources(SimpleNamespace())

    assert result['total'] == 1
    assert result['rows'][0]['id'] == 'source-news'
    assert result['rows'][0]['success_rate'] == 90


@pytest.mark.asyncio
async def test_manual_collection_run_is_persisted_as_queued(monkeypatch):
    source = SimpleNamespace(
        source_id='source-news',
        name='科技资讯源',
        enabled=True,
        status='active',
        config_json={'pageSize': 20},
        schedule_cron=None,
        last_run_time=None,
        last_run_status=None,
        update_time=None,
    )
    query_db = SimpleNamespace(commit=AsyncMock())
    add_run = AsyncMock()
    monkeypatch.setattr(PipelineDao, 'get_source', AsyncMock(return_value=source))
    monkeypatch.setattr(PipelineDao, 'add_collection_run', add_run)

    result = await PipelineDomainService.queue_collection_run(query_db, source.source_id)

    assert result['status'] == 'queued'
    assert source.last_run_status == 'queued'
    add_run.assert_awaited_once()
    query_db.commit.assert_awaited_once()

