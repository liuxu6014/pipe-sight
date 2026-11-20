"""报告导出文件的受控本地存储。"""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from config.env import UploadConfig


class ReportExportStorage:
    """将导出文件保存到上传根目录之外的受控子目录。"""

    _prefix = 'report_exports'

    @classmethod
    def build_key(cls, export_id: str, file_format: str, year: int, month: int, day: int) -> str:
        return f'{cls._prefix}/{year:04d}/{month:02d}/{day:02d}/{export_id}.{file_format}'

    @classmethod
    def _resolve(cls, file_key: str) -> Path:
        root = Path(UploadConfig.UPLOAD_PATH).resolve()
        export_root = (root / cls._prefix).resolve()
        candidate = (root / file_key).resolve()
        if (
            root not in export_root.parents
            or export_root not in candidate.parents
            or not file_key.startswith(f'{cls._prefix}/')
        ):
            raise ValueError('导出文件存储键无效')
        return candidate

    @classmethod
    def write(cls, file_key: str, content: bytes) -> None:
        target = cls._resolve(file_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f'.{uuid4().hex}.writing')
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def cleanup_directory(cls) -> Path:
        return cls._resolve(f'{cls._prefix}/.cleanup')

    @classmethod
    def schedule_cleanup(cls, file_key: str) -> None:
        cls._resolve(file_key)
        cls.write(cls.cleanup_marker(file_key), file_key.encode())

    @classmethod
    def cleanup_marker(cls, file_key: str) -> str:
        marker = sha256(file_key.encode()).hexdigest()
        return f'{cls._prefix}/.cleanup/{marker}'

    @classmethod
    def finish_cleanup(cls, file_key: str) -> None:
        cls.remove(file_key)
        cls.remove(cls.cleanup_marker(file_key))

    @classmethod
    def remove(cls, file_key: str) -> None:
        cls._resolve(file_key).unlink(missing_ok=True)

    @classmethod
    def read(cls, file_key: str) -> bytes:
        return cls._resolve(file_key).read_bytes()


__all__ = ['ReportExportStorage']
