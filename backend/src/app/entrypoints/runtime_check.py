"""Validate production dependencies before accepting HTTP traffic or claiming tasks."""

import os
import shlex
import shutil
from pathlib import Path

from app.entrypoints.file_scan import scan_file
from app.research.services.pdf_fonts import validate_runtime_fonts

MIN_SIGNING_KEY_LENGTH = 32


def runtime_errors() -> list[str]:
    errors = []
    if os.getenv('FILE_SCAN_MODE', 'external') != 'external':
        errors.append('正式部署必须使用 external 文件扫描')
    command = os.getenv('FILE_SCAN_COMMAND', '').strip()
    try:
        executable = shlex.split(command)[0] if command else ''
    except ValueError:
        executable = ''
    if not executable or not shutil.which(executable):
        errors.append('FILE_SCAN_COMMAND 未配置或扫描程序不存在')
    elif Path(executable).name == 'pipesight-file-scan':
        try:
            code, _ = scan_file(
                None,
                host=os.getenv('FILE_SCAN_HOST', 'pipesight-clamav'),
                port=int(os.getenv('FILE_SCAN_PORT', '3310')),
                timeout=5,
            )
        except ValueError:
            code = 2
        if code:
            errors.append('ClamAV 未就绪，请检查服务及病毒库')
    try:
        validate_runtime_fonts(
            digest_path=os.getenv('PDF_DIGEST_FONT_PATH', ''), cjk_path=os.getenv('PDF_CJK_FONT_PATH', '')
        )
    except ValueError as exc:
        errors.append(str(exc))
    key = os.getenv('JWT_SECRET_KEY', '')
    if not key:
        errors.append('必须显式提供原 JWT_SECRET_KEY，不能丢失已加密的模型凭据')
    elif len(key) < MIN_SIGNING_KEY_LENGTH:
        errors.append('生产密钥过短（少于 32 字符），请提供原 JWT_SECRET_KEY')
    return errors


def main() -> None:
    errors = runtime_errors()
    for error in errors:
        print(error)
    if not errors:
        print('部署依赖检查通过')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
