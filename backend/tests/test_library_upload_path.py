"""The upload controller must not prepend a relative upload root twice."""

import io
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from app.library.api import controller as library_api
from app.library.services.materials import MaterialFileService
from config.env import UploadConfig


@pytest.mark.asyncio
async def test_upload_controller_resolves_relative_root_once(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', 'vf_admin/upload_path')
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PREFIX', '/profile')
    recorded = {}

    async def create_material(db, **kwargs):
        recorded.update(kwargs)
        path = MaterialFileService.safe_local_path(kwargs['local_path'])
        assert path is not None and path.is_file()
        assert path.read_text() == 'basket upload test'
        assert MaterialFileService.safe_local_path('../outside.txt') is None
        return {'id': '99'}

    monkeypatch.setattr(library_api.MaterialApiService, 'create_material', create_material)
    await library_api.upload_pipeline_knowledge_document(
        request=SimpleNamespace(base_url='http://localhost/'),
        query_db=None,
        current_user=SimpleNamespace(user=SimpleNamespace(user_id=7, nick_name='测试', user_name='test')),
        file=UploadFile(file=io.BytesIO(b'basket upload test'), filename='test.txt'),
        category='内部资料',
        permission_scope='private',
        tags='',
    )
    assert recorded['local_path'].startswith('/profile/upload/')
