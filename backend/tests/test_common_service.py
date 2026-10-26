import io
import os
from pathlib import Path

import aiofiles
import pytest
from fastapi import BackgroundTasks, UploadFile

from app.infrastructure.services.file_transfer import FileTransferService
from config.env import UploadConfig
from exceptions.exception import ServiceException


@pytest.mark.asyncio
async def test_common_upload_strips_client_path_components(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(UploadConfig, "UPLOAD_PATH", str(tmp_path))
    monkeypatch.setattr(UploadConfig, "UPLOAD_PREFIX", "/profile")
    monkeypatch.setattr(UploadConfig, "UPLOAD_MACHINE", "T")
    upload = UploadFile(file=io.BytesIO(b"safe content"), filename="../../safe.txt")

    result = await FileTransferService.upload_service(
        "http://test/",
        upload,
    )

    stored = result.result
    assert stored is not None
    assert stored.original_filename == "../../safe.txt"
    assert ".." not in stored.new_file_name
    files = [
        os.path.join(root, name)
        for root, _, names in os.walk(tmp_path)
        for name in names
    ]
    assert len(files) == 1
    async with aiofiles.open(files[0], "rb") as stored_file:
        assert await stored_file.read() == b"safe content"


@pytest.mark.asyncio
async def test_common_download_rejects_absolute_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(UploadConfig, "DOWNLOAD_PATH", str(tmp_path))

    with pytest.raises(ServiceException) as exc_info:
        await FileTransferService.download_services(
            BackgroundTasks(),
            "/etc/passwd",
            False,
        )
    assert exc_info.value.message == "文件名称不合法"


@pytest.mark.asyncio
async def test_common_download_rejects_symlink_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    upload_root = os.path.join(tmp_path, "uploads")
    outside_file = os.path.join(tmp_path, "outside.txt")
    os.makedirs(upload_root)
    async with aiofiles.open(outside_file, "wb") as stored_file:
        await stored_file.write(b"outside content")
    os.symlink(outside_file, os.path.join(upload_root, "safe.txt"))
    monkeypatch.setattr(UploadConfig, "DOWNLOAD_PATH", upload_root)

    with pytest.raises(ServiceException) as exc_info:
        await FileTransferService.download_services(
            BackgroundTasks(),
            "safe.txt",
            False,
        )
    assert exc_info.value.message == "文件名称不合法"


@pytest.mark.asyncio
async def test_common_resource_download_rejects_path_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(UploadConfig, "UPLOAD_PATH", str(tmp_path))
    monkeypatch.setattr(UploadConfig, "UPLOAD_PREFIX", "/profile")

    with pytest.raises(ServiceException) as exc_info:
        await FileTransferService.download_resource_services(
            "/profile/upload/../../outside.txt"
        )
    assert exc_info.value.message == "文件名称不合法"
