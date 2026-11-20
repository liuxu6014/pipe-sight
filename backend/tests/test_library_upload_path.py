"""The upload controller must not prepend a relative upload root twice."""

import io
from types import SimpleNamespace

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.library.api import controller as library_api
from app.library.services.materials import MaterialFileService
from config.env import UploadConfig
from exceptions.exception import ServiceException


@pytest.mark.asyncio
async def test_upload_controller_resolves_relative_root_once(tmp_path, monkeypatch) -> None:
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


@pytest.mark.asyncio
async def test_rejected_public_upload_does_not_leave_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    with pytest.raises(ServiceException) as rejected:
        await library_api.upload_pipeline_knowledge_document(
            SimpleNamespace(base_url='http://test/'),
            None,
            SimpleNamespace(user=SimpleNamespace(nick_name='测试用户', user_name='test', user_id=7)),
            UploadFile(io.BytesIO(b'synthetic file'), filename='audit.txt'),
            permission_scope='public',
        )
    assert '暂不支持公开共享' in rejected.value.message
    assert not list(tmp_path.rglob('*'))


@pytest.mark.asyncio
async def test_classification_endpoint_requires_explicit_boolean_consent():
    for value in ({}, {'consent': 1}, {'consent': 'true'}):
        with pytest.raises(ValidationError):
            library_api.MaterialClassificationConsent.model_validate(value)

    with pytest.raises(ServiceException) as rejected:
        await library_api.retry_pipeline_knowledge_classification(
            101, library_api.MaterialClassificationConsent(consent=False), None, None
        )
    assert '须确认' in rejected.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [ServiceException(message='unsupported content'), RuntimeError('database failed')])
async def test_create_failure_removes_new_upload_without_masking_failure(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))

    async def rejected(*_args, **_kwargs):
        assert list(tmp_path.rglob('*.txt'))
        raise failure

    monkeypatch.setattr(library_api.MaterialApiService, 'create_material', rejected)
    with pytest.raises(type(failure)) as observed:
        await library_api.upload_pipeline_knowledge_document(
            SimpleNamespace(base_url='http://test/'),
            None,
            SimpleNamespace(user=SimpleNamespace(nick_name='测试', user_name='test', user_id=7)),
            UploadFile(io.BytesIO(b'synthetic file'), filename='audit.txt'),
            tags='',
        )
    assert observed.value is failure
    assert not list(tmp_path.rglob('*.txt'))


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_replace_original_upload_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    failure = RuntimeError('original database failure')

    async def rejected(*_args, **_kwargs):
        raise failure

    class Unremovable:
        def unlink(self, **_kwargs):
            raise OSError('synthetic cleanup failure')

    monkeypatch.setattr(library_api.MaterialApiService, 'create_material', rejected)
    monkeypatch.setattr(library_api.MaterialFileService, 'safe_local_path', lambda _: Unremovable())
    with pytest.raises(RuntimeError) as observed:
        await library_api.upload_pipeline_knowledge_document(
            SimpleNamespace(base_url='http://test/'),
            None,
            SimpleNamespace(user=SimpleNamespace(nick_name='测试', user_name='test', user_id=7)),
            UploadFile(io.BytesIO(b'synthetic file'), filename='audit.txt'),
            tags='',
        )
    assert observed.value is failure
