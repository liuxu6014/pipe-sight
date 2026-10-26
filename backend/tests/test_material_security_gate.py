"""规范资料状态下继续执行安全门、文件边界和编辑保护。"""

import zipfile
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from test_research_simplified_20261025 import db as refactor_db
from test_research_simplified_20261025 import env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network
from test_research_simplified_20261025 import raises, seed

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
@pytest.mark.parametrize('scan_status', ['pending', 'quarantined', 'failed'])
async def test_upload_cannot_become_usable_before_clean_scan(env, db, tmp_path, monkeypatch, scan_status):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    path = tmp_path / '资料.md'
    path.write_text('合法资料', encoding='utf-8')
    result = await env.materials.MaterialService.create_material(
        db,
        user_id=7,
        name='资料.md',
        file_path=str(path),
        local_path=str(path),
        scanner=lambda *_: NS(status=scan_status),
    )
    row = await db.get(env.material.PipelineMaterial, int(result['id']))
    assert row.status == 'failed' and row.extracted_text is None and row.edited_text is None
    assert result['parseStatus'] == 'failed' and '安全扫描' in result['parseMessage']


@pytest.mark.asyncio
async def test_clean_file_is_queued_not_ready_at_upload(env, db, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    path = tmp_path / '资料.md'
    path.write_text('有效正文', encoding='utf-8')
    parser = AsyncMock(side_effect=AssertionError('API must not parse during upload'))
    result = await env.materials.MaterialService.create_material(
        db, user_id=7, name='资料.md', local_path=str(path), scanner=lambda *_: NS(status='clean'), parser=parser
    )
    assert result['parseStatus'] == 'queued' and result['extractedText'] == ''
    parser.assert_not_called()


@pytest.mark.asyncio
async def test_download_requires_owner_and_clean_scan(env, db, tmp_path, monkeypatch):
    _, row = seed(env, db)
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    path = tmp_path / 'a.txt'
    path.write_text('正文')
    monkeypatch.setattr(env.materials.FileScanService, 'scan', lambda *_: NS(status='quarantined'))
    with raises(env, '无权'):
        await env.materials.MaterialService.get_download(db, 8, row.id)
    with raises(env, '安全扫描'):
        await env.materials.MaterialService.get_download(db, 7, row.id)


def test_parser_path_and_file_type_limits(env, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    assert env.materials.MaterialFileService.safe_local_path('../outside.txt') is None
    executable = tmp_path / 'fake.txt'
    executable.write_bytes(b'MZnot text')
    with raises(env, '文件类型'):
        env.materials.MaterialService.detect_mime(executable, 'fake.txt')
    assert env.materials.MaterialFileService.parse(str(executable), 'legacy.doc', requested_at='offline')[0] == 'failed'


def test_docx_archive_expansion_limit_remains_enforced(env, tmp_path, monkeypatch):
    path = tmp_path / 'oversized.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', 'x' * 100)
    monkeypatch.setattr(env.materials.MaterialFileService, 'max_archive_uncompressed_bytes', 16)
    with zipfile.ZipFile(path) as archive, pytest.raises(ValueError):
        env.materials.MaterialFileService._validate_docx_archive(archive)


@pytest.mark.asyncio
async def test_reparse_preserves_edited_text_and_original_filename(env, db):
    _, row = seed(env, db)
    row.status = 'failed'
    row.edited_text = '用户编辑'
    row.name = '改名后的资料'
    await db.commit()
    result = await env.materials.MaterialService.retry_parse(db, 7, row.id)
    assert result['editedText'] == '用户编辑' and result['fileName'] == 'a.txt' and result['parseStatus'] == 'queued'
