"""上传文件的可选恶意文件扫描适配器。

扫描器不是文件头校验的别名。未配置外部扫描命令时，结果保持 ``pending``，
调用方必须阻止解析、下载和 AI 使用。命令通过参数列表执行，不启用 shell。
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.env import UploadConfig


@dataclass(frozen=True, slots=True)
class FileScanResult:
    """一次扫描的可持久化结果。"""

    status: str
    message: str
    scanner_name: str
    signature: str | None = None
    scanned_at: datetime | None = None


class FileScanService:
    """执行外部扫描或显式启用的本地基础检查。

    ``basic`` 模式只用于开发/验收环境，不能替代 ClamAV 等带病毒库的扫描器。
    """

    _output_limit = 240
    _executable_signatures = (
        b'MZ',  # Windows PE
        b'\x7fELF',  # Linux ELF
        b'\xfe\xed\xfa\xce',  # Mach-O 32-bit
        b'\xce\xfa\xed\xfe',
        b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit
        b'\xcf\xfa\xed\xfe',
    )

    @classmethod
    def scan(cls, local_path: str | None, _original_name: str = '') -> FileScanResult:
        if not local_path or not Path(local_path).is_file():
            return FileScanResult('failed', '源文件不存在，无法完成安全扫描。', 'file-scan', scanned_at=datetime.now())
        path = Path(local_path).resolve()
        if UploadConfig.FILE_SCAN_MODE == 'basic':
            return cls._basic_scan(path)
        command_text = UploadConfig.FILE_SCAN_COMMAND
        if not command_text:
            return FileScanResult(
                'pending',
                '未配置恶意文件扫描引擎，资料暂不进入解析、下载或 AI 使用。',
                'unconfigured',
            )
        try:
            command = [*shlex.split(command_text), str(path)]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=UploadConfig.FILE_SCAN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return FileScanResult(
                'failed',
                '恶意文件扫描超时，资料暂不可用。',
                command[0] if 'command' in locals() and command else 'configured',
                scanned_at=datetime.now(),
            )
        except (OSError, ValueError) as exc:
            return FileScanResult(
                'failed',
                f'恶意文件扫描执行失败：{str(exc)[: cls._output_limit]}',
                'configured',
                scanned_at=datetime.now(),
            )

        output = ' '.join((completed.stdout or '').split()) or ' '.join((completed.stderr or '').split())
        output = output[: cls._output_limit]
        scanner_name = command[0] if command else 'configured'
        if completed.returncode == 0:
            return FileScanResult('clean', '文件已通过恶意文件扫描。', scanner_name, output or None, datetime.now())
        if completed.returncode == 1:
            return FileScanResult('quarantined', '扫描发现风险，文件已禁止解析、下载和 AI 使用。', scanner_name, output or None, datetime.now())
        return FileScanResult(
            'failed',
            f'恶意文件扫描未完成{f"：{output}" if output else ""}，资料暂不可用。',
            scanner_name,
            output or None,
            datetime.now(),
        )

    @classmethod
    def _basic_scan(cls, path: Path) -> FileScanResult:
        """执行不依赖外部程序的基础检查。

        该检查只识别常见可执行文件头并校验文件大小，不能检查压缩包内部内容、宏、
        脚本行为或病毒特征库；因此结果会明确标注能力边界。
        """

        try:
            if path.stat().st_size > UploadConfig.MAX_UPLOAD_BYTES:
                return FileScanResult(
                    'failed', '文件超过允许的最大大小，基础检查未通过。', 'builtin-basic', scanned_at=datetime.now()
                )
            with path.open('rb') as source:
                header = source.read(16)
        except OSError as exc:
            return FileScanResult(
                'failed', f'基础文件检查失败：{str(exc)[: cls._output_limit]}', 'builtin-basic', scanned_at=datetime.now()
            )

        if any(header.startswith(signature) for signature in cls._executable_signatures):
            return FileScanResult(
                'quarantined',
                '基础检查发现可执行文件特征，资料已禁止解析、下载和 AI 使用。',
                'builtin-basic',
                'executable-signature',
                datetime.now(),
            )
        return FileScanResult(
            'clean',
            '基础文件检查通过；当前未启用带病毒库的专业扫描器。',
            'builtin-basic',
            scanned_at=datetime.now(),
        )


__all__ = ['FileScanResult', 'FileScanService']
