from types import SimpleNamespace as NS

import pytest
from test_research_simplified_20261025 import db as refactor_db, env as refactor_env
from test_research_simplified_20261025 import no_external_network as refactor_no_external_network

env = refactor_env
db = refactor_db
no_external_network = refactor_no_external_network


@pytest.mark.asyncio
async def test_upload_reuses_same_owner_and_bytes_but_not_name_or_other_owner(env, db, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    paths = []

    async def upload(name, content, owner=7):
        path = tmp_path / f'{len(paths)}-{name}'
        paths.append(path)
        path.write_text(content, encoding='utf-8')
        return await env.materials.MaterialService.create_material(
            db, user_id=owner, name=name, local_path=str(path), scanner=lambda *_: NS(status='clean')
        )

    first = await upload('a.txt', '相同内容')
    second = await upload('renamed.txt', '相同内容')
    assert second['id'] == first['id'] and second['duplicate'] is True
    assert first['fileHash'] == second['fileHash']
    assert paths[0].is_file() and not paths[1].exists()
    different = await upload('a.txt', '不同内容')
    assert different['id'] != first['id']
    other_owner = await upload('other.txt', '相同内容', owner=8)
    assert other_owner['id'] != first['id']


@pytest.mark.asyncio
async def test_edited_document_is_not_overwritten_or_reused_as_original(env, db, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    path = tmp_path / 'a.txt'
    path.write_text('原文', encoding='utf-8')
    first = await env.materials.MaterialService.create_material(db, user_id=7, name='a.txt', local_path=str(path), scanner=lambda *_: NS(status='clean'))
    row = await db.get(env.material.PipelineMaterial, int(first['id']))
    row.edited_text = '修订正文'
    await db.commit()
    second = await env.materials.MaterialService.create_material(db, user_id=7, name='a.txt', local_path=str(path), scanner=lambda *_: NS(status='clean'))
    assert second['id'] != first['id']
    assert env.materials.MaterialService.material_dict(row, 7)['editHash']


@pytest.mark.asyncio
async def test_clean_duplicate_requeues_failed_parse_without_creating_another_record(env, db, tmp_path, monkeypatch):
    monkeypatch.setattr(env.cfg.UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    original = tmp_path / 'a.txt'
    original.write_text('正文', encoding='utf-8')
    first = await env.materials.MaterialService.create_material(db, user_id=7, name='a.txt', local_path=str(original), scanner=lambda *_: NS(status='clean'))
    row = await db.get(env.material.PipelineMaterial, int(first['id']))
    row.status, row.error = 'failed', '旧解析失败'
    await db.commit()
    copy = tmp_path / 'copy.txt'
    copy.write_text('正文', encoding='utf-8')
    result = await env.materials.MaterialService.create_material(db, user_id=7, name='copy.txt', local_path=str(copy), scanner=lambda *_: NS(status='clean'))
    assert result['id'] == first['id'] and result['parseStatus'] == 'queued'
    assert result['duplicate'] is True and original.exists() and not copy.exists()
