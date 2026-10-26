import hashlib
import io
import os
from pathlib import Path

import aiofiles
import pytest
from fastapi import UploadFile

from app.system.services.files import FileStorageService
from config.env import UploadConfig
from exceptions.exception import ServiceException


@pytest.mark.asyncio
async def test_upload_strips_path_components_from_client_filename(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PREFIX', '/profile')
    monkeypatch.setattr(UploadConfig, 'UPLOAD_MACHINE', 'T')

    upload = UploadFile(file=io.BytesIO(b'protected content'), filename='../../safe.txt')
    stored = await FileStorageService.upload('http://test/', upload)

    assert stored.original_filename == '../../safe.txt'
    assert stored.file_name.startswith('/profile/upload/')
    assert stored.new_file_name.endswith('.txt')
    assert '..' not in stored.new_file_name
    assert stored.file_size == len(b'protected content')
    assert stored.file_hash == hashlib.sha256(b'protected content').hexdigest()
    files = [
        os.path.join(root, name)
        for root, _, names in os.walk(tmp_path)
        for name in names
    ]
    assert len(files) == 1
    async with aiofiles.open(files[0], 'rb') as stored_file:
        assert await stored_file.read() == b'protected content'


@pytest.mark.asyncio
async def test_upload_rejects_empty_file_and_leaves_no_upload_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    upload = UploadFile(file=io.BytesIO(b''), filename='empty.txt')

    with pytest.raises(ServiceException) as exc_info:
        await FileStorageService.upload('http://test/', upload)

    assert exc_info.value.message == '文件不能为空'
    assert not any(name for root, _, names in os.walk(tmp_path) for name in names)


@pytest.mark.asyncio
async def test_upload_rejects_content_disguised_as_pdf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    upload = UploadFile(file=io.BytesIO(b'plain text'), filename='fake.pdf')

    with pytest.raises(ServiceException) as exc_info:
        await FileStorageService.upload('http://test/', upload)

    assert exc_info.value.message == '文件内容与扩展名不一致'
    assert not any(name.endswith('.pdf') for root, _, names in os.walk(tmp_path) for name in names)


@pytest.mark.asyncio
async def test_upload_rejects_file_over_configured_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    monkeypatch.setattr(UploadConfig, 'MAX_UPLOAD_BYTES', 4)
    upload = UploadFile(file=io.BytesIO(b'12345'), filename='too-large.txt')

    with pytest.raises(ServiceException) as exc_info:
        await FileStorageService.upload('http://test/', upload)

    assert exc_info.value.message == '文件超过 1 MB 大小限制'
    assert not any(name for root, _, names in os.walk(tmp_path) for name in names)


@pytest.mark.asyncio
async def test_upload_supports_route_specific_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(UploadConfig, 'UPLOAD_PATH', str(tmp_path))
    upload = UploadFile(file=io.BytesIO(b'12345'), filename='too-large-for-route.txt')

    with pytest.raises(ServiceException) as exc_info:
        await FileStorageService.upload('http://test/', upload, max_bytes=4)

    assert exc_info.value.message == '文件超过 1 MB 大小限制'
    assert not any(name for root, _, names in os.walk(tmp_path) for name in names)
