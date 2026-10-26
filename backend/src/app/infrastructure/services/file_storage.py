"""受控上传文件存储服务。

该服务只负责把上传内容安全写入配置的上传根目录并返回存储结果；资料
数据库记录和解析流程由 ``app.library`` 负责。
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import aiofiles

from app.infrastructure.services.file_upload import FileUploadSupport
from common.ports.files import UploadFilePort
from config.env import UploadConfig
from exceptions.exception import ServiceException


@dataclass(frozen=True, slots=True)
class StoredUpload:
    """上传结果，不暴露管理模块的响应模型。"""

    file_name: str
    new_file_name: str
    original_filename: str | None
    url: str
    file_size: int
    file_hash: str


class FileStorageService:
    """将用户上传内容写入受控目录。"""

    _header_length = 4096
    _text_extensions = frozenset({'html', 'htm', 'md', 'txt'})
    _magic_signatures = {
        'bmp': (b'BM',),
        'gif': (b'GIF87a', b'GIF89a'),
        'jpg': (b'\xff\xd8\xff',),
        'jpeg': (b'\xff\xd8\xff',),
        'png': (b'\x89PNG\r\n\x1a\n',),
        'pdf': (b'%PDF-',),
        'doc': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
        'xls': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
        'ppt': (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',),
        'zip': (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'),
        'docx': (b'PK\x03\x04',),
        'xlsx': (b'PK\x03\x04',),
        'pptx': (b'PK\x03\x04',),
        'rar': (b'Rar!\x1a\x07',),
        'gz': (b'\x1f\x8b',),
        'bz2': (b'BZh',),
        'avi': (b'RIFF',),
        'rmvb': (b'.RMF',),
    }

    @classmethod
    def _validate_header(cls, extension: str, header: bytes) -> None:
        if extension in cls._text_extensions:
            return
        signatures = cls._magic_signatures.get(extension)
        if not signatures or not any(header.startswith(signature) for signature in signatures):
            raise ServiceException(message='文件内容与扩展名不一致')

    @classmethod
    async def upload(
        cls,
        base_url: str,
        file: UploadFilePort,
        *,
        max_bytes: int | None = None,
    ) -> StoredUpload:
        if not FileUploadSupport.check_file_extension(file):
            raise ServiceException(message='文件类型不合法')

        now = datetime.now()
        relative_path = f'upload/{now:%Y}/{now:%m}/{now:%d}'
        directory = Path(UploadConfig.UPLOAD_PATH) / relative_path
        directory.mkdir(parents=True, exist_ok=True)

        original_name = Path(file.filename or 'upload').name
        stem, separator, suffix = original_name.rpartition('.')
        if not separator:
            stem, suffix = original_name, 'bin'
        suffix = suffix.lower()
        filename = (
            f'{stem}_{now:%Y%m%d%H%M%S}{UploadConfig.UPLOAD_MACHINE}'
            f'{FileUploadSupport.generate_random_number()}.{suffix}'
        )
        filepath = directory / filename
        temporary_path = directory / f'.{uuid4().hex}.uploading'
        total_size = 0
        header = b''
        digest = hashlib.sha256()
        size_limit = max_bytes or UploadConfig.MAX_UPLOAD_BYTES
        try:
            async with aiofiles.open(temporary_path, 'wb') as target:
                while chunk := await file.read(1024 * 1024):
                    total_size += len(chunk)
                    if total_size > size_limit:
                        limit_mb = max(1, (size_limit + 1024 * 1024 - 1) // (1024 * 1024))
                        raise ServiceException(message=f'文件超过 {limit_mb} MB 大小限制')
                    if not header:
                        header = chunk[: cls._header_length]
                    digest.update(chunk)
                    await target.write(chunk)
            if total_size == 0:
                raise ServiceException(message='文件不能为空')
            cls._validate_header(suffix, header)
            os.replace(temporary_path, filepath)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        mapped_path = f'{UploadConfig.UPLOAD_PREFIX}/{relative_path}/{filename}'
        return StoredUpload(
            file_name=mapped_path,
            new_file_name=filename,
            original_filename=file.filename,
            url=f'{base_url}{UploadConfig.UPLOAD_PREFIX[1:]}/{relative_path}/{filename}',
            file_size=total_size,
            file_hash=digest.hexdigest(),
        )


__all__ = ['FileStorageService', 'StoredUpload']
